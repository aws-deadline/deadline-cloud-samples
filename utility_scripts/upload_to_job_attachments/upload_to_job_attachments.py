#!/usr/bin/env python3
"""
Upload files and directories from local workstation to AWS Deadline Cloud job attachments storage.

This script uploads files to the job attachments S3 bucket in content-addressable storage format,
allowing subsequent jobs to use the data without re-uploading.
"""

import argparse
import os
import sys
import threading
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from pathlib import Path
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
)

try:
    from xxhash import xxh3_128
except ImportError:
    print(
        "Error: xxhash library is required. Install with: pip install xxhash",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import boto3
    from boto3.s3.transfer import TransferConfig
    from botocore.exceptions import (
        BotoCoreError,
        ClientError,
    )
except ImportError:
    print(
        "Error: boto3 library is required. Install with: pip install boto3",
        file=sys.stderr,
    )
    sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Upload files to AWS Deadline Cloud job attachments storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload using direct S3 specification
  %(prog)s --s3-bucket my-bucket --s3-prefix job-attachments --paths /path/to/files /path/to/dir

  # Upload using queue lookup
  %(prog)s --farm-id farm-123 --queue-id queue-456 --paths /path/to/files

  # Upload with custom thread count
  %(prog)s --s3-bucket my-bucket --s3-prefix job-attachments --paths /data --threads 8
        """,
    )

    # S3 Configuration - Option 1: Direct specification
    s3_group = parser.add_argument_group("S3 Direct Configuration")
    s3_group.add_argument(
        "--s3-bucket",
        help="S3 bucket name for job attachments",
    )
    s3_group.add_argument(
        "--s3-prefix",
        help='S3 root prefix for job attachments (e.g., "job-attachments" or "farm-123/queue-456")',
    )

    # S3 Configuration - Option 2: Queue lookup
    queue_group = parser.add_argument_group("Queue Configuration Lookup")
    queue_group.add_argument(
        "--farm-id",
        help="AWS Deadline Cloud Farm ID",
    )
    queue_group.add_argument(
        "--queue-id",
        help="AWS Deadline Cloud Queue ID",
    )

    # Required arguments
    parser.add_argument(
        "--paths",
        nargs="+",
        required=True,
        help="File and/or directory paths to upload (space-separated)",
    )

    # Optional arguments
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
        help="Number of concurrent upload threads (default: 4)",
    )
    parser.add_argument(
        "--profile",
        help="AWS profile name to use",
    )
    parser.add_argument(
        "--region",
        help="AWS region (overrides default region)",
    )
    
    # Transfer configuration options
    transfer_group = parser.add_argument_group('S3 Transfer Configuration')
    transfer_group.add_argument(
        "--multipart-threshold",
        type=int,
        help="File size threshold in MB for multipart uploads (default: 8 MB)",
    )
    transfer_group.add_argument(
        "--multipart-chunksize",
        type=int,
        help="Chunk size in MB for multipart uploads (default: 8 MB)",
    )
    transfer_group.add_argument(
        "--max-concurrency",
        type=int,
        help="Max concurrent requests per file for multipart uploads (default: 10)",
    )
    transfer_group.add_argument(
        "--max-bandwidth",
        type=int,
        help="Maximum bandwidth in MB/s for uploads (optional throttling)",
    )

    args = parser.parse_args()

    # Validate mutually exclusive S3 configuration options
    has_direct_config = args.s3_bucket or args.s3_prefix
    has_queue_config = args.farm_id or args.queue_id

    if has_direct_config and has_queue_config:
        parser.error(
            "Cannot specify both direct S3 configuration (--s3-bucket/--s3-prefix) "
            "and queue lookup (--farm-id/--queue-id). Choose one method."
        )

    if not has_direct_config and not has_queue_config:
        parser.error(
            "Must specify either direct S3 configuration (--s3-bucket and --s3-prefix) "
            "or queue lookup (--farm-id and --queue-id)"
        )

    # Validate direct S3 configuration is complete
    if has_direct_config:
        if not args.s3_bucket:
            parser.error("--s3-bucket is required when using direct S3 configuration")
        if not args.s3_prefix:
            parser.error("--s3-prefix is required when using direct S3 configuration")

    # Validate queue configuration is complete
    if has_queue_config:
        if not args.farm_id:
            parser.error("--farm-id is required when using queue lookup")
        if not args.queue_id:
            parser.error("--queue-id is required when using queue lookup")

    # Validate thread count
    if args.threads < 1:
        parser.error("--threads must be at least 1")

    return args


def retry_with_backoff(
    func,
    max_retries=3,
    initial_delay=1.0,
):
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry (should be a callable with no arguments)
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds

    Returns:
        Result of the function

    Raises:
        Last exception if all retries fail
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except (
            BotoCoreError,
            ClientError,
        ) as e:
            last_exception = e
            if attempt < max_retries - 1:
                print(
                    f"  Retry attempt {attempt + 1}/{max_retries} after {delay}s delay...",
                    file=sys.stderr,
                )
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise last_exception


def get_s3_settings_direct(bucket: str, prefix: str) -> Tuple[str, str]:
    """
    Get S3 settings from direct specification.

    Args:
        bucket: S3 bucket name
        prefix: S3 root prefix

    Returns:
        Tuple of (bucket, prefix)

    Raises:
        ValueError: If inputs are invalid
    """
    if not bucket or not bucket.strip():
        raise ValueError("S3 bucket name cannot be empty")
    if not prefix or not prefix.strip():
        raise ValueError("S3 prefix cannot be empty")

    # Remove leading/trailing slashes from prefix
    prefix = prefix.strip("/")

    return (bucket.strip(), prefix)


def get_s3_settings_from_queue(
    session: boto3.Session,
    farm_id: str,
    queue_id: str,
) -> Tuple[str, str]:
    """
    Get S3 settings from Deadline Cloud queue configuration.

    Args:
        session: Boto3 session
        farm_id: Farm ID
        queue_id: Queue ID

    Returns:
        Tuple of (bucket, prefix)

    Raises:
        ValueError: If queue doesn't have job attachments configured
        ClientError: If API call fails
    """
    deadline_client = session.client("deadline")

    try:
        response = deadline_client.get_queue(
            farmId=farm_id,
            queueId=queue_id,
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        raise ValueError(
            f"Failed to get queue configuration ({error_code}): {error_msg}"
        )

    # Extract job attachment settings
    job_attachment_settings = response.get("jobAttachmentSettings")
    if not job_attachment_settings:
        raise ValueError(
            f"Queue {queue_id} does not have job attachments configured. "
            "Please configure job attachments for this queue or use direct S3 specification."
        )

    bucket = job_attachment_settings.get("s3BucketName")
    prefix = job_attachment_settings.get("rootPrefix")

    if not bucket:
        raise ValueError("Queue job attachment settings missing s3BucketName")
    if not prefix:
        raise ValueError("Queue job attachment settings missing rootPrefix")

    return (bucket, prefix)


class UploadProgressTracker:
    """Thread-safe progress tracker for upload operations."""
    
    def __init__(self, total_files: int, total_bytes: int):
        self.total_files = total_files
        self.total_bytes = total_bytes
        self.bytes_uploaded = 0
        self.bytes_skipped = 0
        self.files_completed = 0
        self.lock = threading.Lock()
        self.last_update_time = time.time()
        self.update_interval = 0.5  # Update display every 0.5 seconds
    
    def update_bytes(self, bytes_amount: int):
        """Update bytes uploaded (called by S3 callback)."""
        with self.lock:
            self.bytes_uploaded += bytes_amount
            self._maybe_print_progress()
    
    def skip_file(self, file_size: int):
        """Mark a file as skipped and adjust total bytes."""
        with self.lock:
            self.bytes_skipped += file_size
            self.files_completed += 1
            self._maybe_print_progress()
    
    def complete_file(self):
        """Mark a file as completed."""
        with self.lock:
            self.files_completed += 1
            self._maybe_print_progress()
    
    def _maybe_print_progress(self):
        """Print progress if enough time has passed (rate limiting)."""
        current_time = time.time()
        if current_time - self.last_update_time >= self.update_interval:
            self._print_progress()
            self.last_update_time = current_time
    
    def _print_progress(self):
        """Print current progress (must be called with lock held)."""
        if self.total_bytes > 0:
            # Adjust total to exclude skipped files
            adjusted_total = self.total_bytes - self.bytes_skipped
            if adjusted_total > 0:
                byte_progress = (self.bytes_uploaded / adjusted_total) * 100
            else:
                byte_progress = 100.0
            
            bytes_mb = self.bytes_uploaded / (1024 * 1024)
            total_mb = adjusted_total / (1024 * 1024)
            print(
                f"  Upload progress: {byte_progress:.1f}% "
                f"({self.files_completed}/{self.total_files} files) - "
                f"{bytes_mb:.2f} MB / {total_mb:.2f} MB"
            )
        else:
            file_progress = (self.files_completed / self.total_files) * 100 if self.total_files > 0 else 0
            print(
                f"  Upload progress: {file_progress:.1f}% "
                f"({self.files_completed}/{self.total_files} files)"
            )
    
    def print_final(self):
        """Print final progress."""
        with self.lock:
            self._print_progress()


def upload_file(
    s3_client,
    file_info: Dict,
    bucket: str,
    prefix: str,
    transfer_config: Optional[TransferConfig] = None,
    progress_tracker: Optional[UploadProgressTracker] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Upload a file to S3 if it doesn't already exist, with retry logic.

    Args:
        s3_client: Boto3 S3 client
        file_info: Dict with path, size, mtime, hash
        bucket: S3 bucket name
        prefix: S3 root prefix
        transfer_config: Optional TransferConfig for upload customization
        progress_tracker: Optional progress tracker for byte-level progress

    Returns:
        Tuple of (was_uploaded: bool, error_message: Optional[str])
    """
    file_hash = file_info["hash"]
    file_path = file_info["path"]

    # Construct S3 key in content-addressable format
    s3_key = f"{prefix}/Data/{file_hash}.xxh128"

    try:
        # Check if file already exists in S3 (with retry)
        def check_exists():
            try:
                s3_client.head_object(
                    Bucket=bucket,
                    Key=s3_key,
                )
                return True
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code == "404":
                    return False
                raise

        exists = retry_with_backoff(check_exists)
        if exists:
            # File exists, skip upload
            return (False, None)

        # Upload file to S3 (with retry)
        def do_upload():
            # Create callback for progress tracking
            callback = None
            if progress_tracker:
                callback = lambda bytes_amount: progress_tracker.update_bytes(bytes_amount)
            
            s3_client.upload_file(
                Filename=file_path,
                Bucket=bucket,
                Key=s3_key,
                Config=transfer_config,
                Callback=callback,
            )

        retry_with_backoff(do_upload)
        return (True, None)

    except Exception as e:
        error_msg = f"Failed to upload {file_path}: {e}"
        return (False, error_msg)


def compute_hash(file_path: str) -> str:
    """
    Compute xxh128 hash for a file using streaming to handle large files.

    Args:
        file_path: Path to the file

    Returns:
        Hexadecimal hash string

    Raises:
        OSError: If file cannot be read
    """
    hasher = xxh3_128()

    # Stream file in chunks to avoid loading entire file into memory
    chunk_size = 1024 * 1024  # 1 MB chunks

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)

    return hasher.hexdigest()


def upload_files_parallel(
    s3_client,
    files: List[Dict],
    bucket: str,
    prefix: str,
    num_threads: int,
    transfer_config: Optional[TransferConfig] = None,
) -> Dict:
    """
    Upload multiple files to S3 in parallel using thread pool.

    Args:
        s3_client: Boto3 S3 client
        files: List of file info dicts (path, size, mtime, hash)
        bucket: S3 bucket name
        prefix: S3 root prefix
        num_threads: Number of threads to use
        transfer_config: Optional TransferConfig for upload customization

    Returns:
        Dict with upload statistics
    """
    uploaded_files = []
    skipped_files = []
    failed_files = []
    total_bytes_uploaded = 0
    
    # Create progress tracker
    total_bytes = sum(f["size"] for f in files)
    progress_tracker = UploadProgressTracker(len(files), total_bytes)

    def upload_single_file(
        file_info: Dict,
    ) -> Tuple[str, bool, Optional[str], int]:
        """Helper function to upload a single file."""
        (
            was_uploaded,
            error,
        ) = upload_file(
            s3_client,
            file_info,
            bucket,
            prefix,
            transfer_config,
            progress_tracker,
        )
        bytes_uploaded = file_info["size"] if was_uploaded else 0
        
        # Update progress tracker based on result
        if was_uploaded:
            # File was uploaded, complete_file already called
            progress_tracker.complete_file()
        elif not error:
            # File was skipped (already exists)
            progress_tracker.skip_file(file_info["size"])
        else:
            # File failed, just mark as completed
            progress_tracker.complete_file()
        
        return (
            file_info["path"],
            was_uploaded,
            error,
            bytes_uploaded,
        )

    print(f"Uploading {len(files)} files using {num_threads} threads...")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {
            executor.submit(
                upload_single_file,
                file_info,
            ): file_info
            for file_info in files
        }

        completed = 0
        for future in as_completed(futures):
            (
                file_path,
                was_uploaded,
                error,
                bytes_uploaded,
            ) = future.result()

            if error:
                failed_files.append(
                    {
                        "path": file_path,
                        "error": error,
                    }
                )
                print(
                    f"  Failed: {file_path}",
                    file=sys.stderr,
                )
            elif was_uploaded:
                uploaded_files.append(file_path)
                total_bytes_uploaded += bytes_uploaded
            else:
                skipped_files.append(file_path)

            completed += 1
    
    # Print final progress
    progress_tracker.print_final()
    print(
        f"  Completed: Uploaded: {len(uploaded_files)}, Skipped: {len(skipped_files)}, Failed: {len(failed_files)}"
    )

    return {
        "total_files": len(files),
        "uploaded_files": uploaded_files,
        "skipped_files": skipped_files,
        "failed_files": failed_files,
        "total_bytes_uploaded": total_bytes_uploaded,
    }


def compute_hashes_parallel(files: List[Dict], num_threads: int) -> List[Dict]:
    """
    Compute hashes for multiple files in parallel using thread pool.

    Args:
        files: List of file info dicts (path, size, mtime)
        num_threads: Number of threads to use

    Returns:
        List of file info dicts with added 'hash' key
    """
    hashed_files = []
    failed_files = []

    def hash_file(
        file_info: Dict,
    ) -> Dict:
        """Helper function to hash a single file."""
        try:
            file_hash = compute_hash(file_info["path"])
            return {
                **file_info,
                "hash": file_hash,
            }
        except Exception as e:
            print(
                f"Warning: Failed to hash file {file_info['path']}: {e}",
                file=sys.stderr,
            )
            return None

    print(f"Computing hashes for {len(files)} files using {num_threads} threads...")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {
            executor.submit(hash_file, file_info): file_info for file_info in files
        }

        completed = 0
        for future in as_completed(futures):
            result = future.result()
            if result:
                hashed_files.append(result)
            else:
                failed_files.append(futures[future])

            completed += 1
            if completed % 10 == 0 or completed == len(files):
                progress = (completed / len(files)) * 100
                print(f"  Hashing progress: {progress:.1f}% ({completed}/{len(files)})")

    if failed_files:
        print(
            f"Warning: Failed to hash {len(failed_files)} files",
            file=sys.stderr,
        )

    return hashed_files


def print_summary(
    upload_result: Dict,
    total_files_collected: int,
):
    """
    Print final summary of upload operation.

    Args:
        upload_result: Dict with upload statistics
        total_files_collected: Total number of files collected initially
    """
    print("\n" + "=" * 50)
    print("Upload Summary")
    print("=" * 50)

    print(f"Files collected:     {total_files_collected}")
    print(f"Files processed:     {upload_result['total_files']}")
    print(f"Files uploaded:      {len(upload_result['uploaded_files'])}")
    print(f"Files skipped:       {len(upload_result['skipped_files'])} (already in S3)")
    print(f"Files failed:        {len(upload_result['failed_files'])}")

    # Convert bytes to human-readable format
    bytes_uploaded = upload_result["total_bytes_uploaded"]
    if bytes_uploaded < 1024:
        size_str = f"{bytes_uploaded} B"
    elif bytes_uploaded < 1024 * 1024:
        size_str = f"{bytes_uploaded / 1024:.2f} KB"
    elif bytes_uploaded < 1024 * 1024 * 1024:
        size_str = f"{bytes_uploaded / (1024 * 1024):.2f} MB"
    else:
        size_str = f"{bytes_uploaded / (1024 * 1024 * 1024):.2f} GB"

    print(f"Total bytes uploaded: {size_str}")

    if upload_result["failed_files"]:
        print("\nFailed files:")
        for failed in upload_result["failed_files"]:
            print(f"  - {failed['path']}")
            print(f"    Error: {failed['error']}")


def collect_files(
    paths: List[str],
) -> List[Dict]:
    """
    Recursively collect all files from the given paths.

    Args:
        paths: List of file and/or directory paths

    Returns:
        List of dicts with keys: path (str), size (int), mtime (int nanoseconds)
    """
    collected_files = []

    for path_str in paths:
        path = Path(path_str)

        # Check if path exists
        if not path.exists():
            print(
                f"Warning: Path does not exist, skipping: {path_str}",
                file=sys.stderr,
            )
            continue

        # Check if path is accessible
        try:
            path.stat()
        except PermissionError:
            print(
                f"Warning: Permission denied, skipping: {path_str}",
                file=sys.stderr,
            )
            continue
        except OSError as e:
            print(
                f"Warning: Cannot access path, skipping: {path_str} ({e})",
                file=sys.stderr,
            )
            continue

        # Handle individual file
        if path.is_file():
            try:
                stat_info = path.stat()
                collected_files.append(
                    {
                        "path": str(path.resolve()),
                        "size": stat_info.st_size,
                        "mtime": int(stat_info.st_mtime_ns),
                    }
                )
            except (
                PermissionError,
                OSError,
            ) as e:
                print(
                    f"Warning: Cannot read file, skipping: {path_str} ({e})",
                    file=sys.stderr,
                )
                continue

        # Handle directory recursively
        elif path.is_dir():
            try:
                for (
                    root,
                    dirs,
                    files,
                ) in os.walk(path):
                    # Filter out inaccessible directories
                    dirs[:] = [
                        d
                        for d in dirs
                        if os.access(
                            os.path.join(root, d),
                            os.R_OK,
                        )
                    ]

                    for filename in files:
                        file_path = Path(root) / filename
                        try:
                            stat_info = file_path.stat()
                            collected_files.append(
                                {
                                    "path": str(file_path.resolve()),
                                    "size": stat_info.st_size,
                                    "mtime": int(stat_info.st_mtime_ns),
                                }
                            )
                        except (
                            PermissionError,
                            OSError,
                        ) as e:
                            print(
                                f"Warning: Cannot read file, skipping: {file_path} ({e})",
                                file=sys.stderr,
                            )
                            continue
            except (
                PermissionError,
                OSError,
            ) as e:
                print(
                    f"Warning: Cannot access directory, skipping: {path_str} ({e})",
                    file=sys.stderr,
                )
                continue
        else:
            print(
                f"Warning: Path is neither file nor directory, skipping: {path_str}",
                file=sys.stderr,
            )
            continue

    return collected_files


def main() -> int:
    """
    Main entry point for the upload script.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        args = parse_arguments()

        print("AWS Deadline Cloud Job Attachments Uploader")
        print("=" * 50)

        # Step 1: Get S3 configuration
        print("\n[1/4] Getting S3 configuration...")
        try:
            if args.s3_bucket:
                # Direct S3 specification
                (
                    bucket,
                    prefix,
                ) = get_s3_settings_direct(
                    args.s3_bucket,
                    args.s3_prefix,
                )
                print(f"  Using direct S3 configuration:")
                print(f"    Bucket: {bucket}")
                print(f"    Prefix: {prefix}")
                session = boto3.Session(
                    profile_name=args.profile,
                    region_name=args.region,
                )
            else:
                # Queue lookup
                print(f"  Looking up queue configuration...")
                print(f"    Farm ID: {args.farm_id}")
                print(f"    Queue ID: {args.queue_id}")
                session = boto3.Session(
                    profile_name=args.profile,
                    region_name=args.region,
                )
                (
                    bucket,
                    prefix,
                ) = get_s3_settings_from_queue(
                    session,
                    args.farm_id,
                    args.queue_id,
                )
                print(f"  Retrieved from queue:")
                print(f"    Bucket: {bucket}")
                print(f"    Prefix: {prefix}")
        except Exception as e:
            print(
                f"Error getting S3 configuration: {e}",
                file=sys.stderr,
            )
            return 1

        # Create S3 client
        s3_client = session.client("s3")
        
        # Create TransferConfig if custom settings provided
        transfer_config = None
        if args.multipart_threshold or args.multipart_chunksize or args.max_concurrency or args.max_bandwidth:
            config_kwargs = {}
            if args.multipart_threshold:
                config_kwargs['multipart_threshold'] = args.multipart_threshold * 1024 * 1024  # Convert MB to bytes
            if args.multipart_chunksize:
                config_kwargs['multipart_chunksize'] = args.multipart_chunksize * 1024 * 1024  # Convert MB to bytes
            if args.max_concurrency:
                config_kwargs['max_concurrency'] = args.max_concurrency
            if args.max_bandwidth:
                config_kwargs['max_bandwidth'] = args.max_bandwidth * 1024 * 1024  # Convert MB/s to bytes/s
            
            transfer_config = TransferConfig(**config_kwargs)
            print(f"  Using custom transfer configuration:")
            if args.multipart_threshold:
                print(f"    Multipart threshold: {args.multipart_threshold} MB")
            if args.multipart_chunksize:
                print(f"    Multipart chunk size: {args.multipart_chunksize} MB")
            if args.max_concurrency:
                print(f"    Max concurrency per file: {args.max_concurrency}")
            if args.max_bandwidth:
                print(f"    Max bandwidth: {args.max_bandwidth} MB/s")

        # Verify bucket access
        print(f"  Verifying access to S3 bucket...")
        try:
            s3_client.head_bucket(Bucket=bucket)
            print(f"  ✓ Bucket access confirmed")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                print(
                    f"Error: S3 bucket '{bucket}' does not exist or you don't have access to it",
                    file=sys.stderr,
                )
            elif error_code == "403":
                print(
                    f"Error: Access denied to S3 bucket '{bucket}'. Check your AWS credentials and permissions.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"Error: Cannot access S3 bucket '{bucket}': {e}",
                    file=sys.stderr,
                )
            return 1
        except Exception as e:
            print(
                f"Error: Failed to verify bucket access: {e}",
                file=sys.stderr,
            )
            return 1

        # Step 2: Collect files
        print(f"\n[2/4] Collecting files from {len(args.paths)} path(s)...")
        collected_files = collect_files(args.paths)

        if not collected_files:
            print(
                "Error: No files found to upload",
                file=sys.stderr,
            )
            return 1

        total_size = sum(f["size"] for f in collected_files)
        print(
            f"  Found {len(collected_files)} files ({total_size / (1024*1024):.2f} MB)"
        )

        # Step 3: Compute hashes
        print(f"\n[3/4] Computing file hashes...")
        hashed_files = compute_hashes_parallel(
            collected_files,
            args.threads,
        )

        if not hashed_files:
            print(
                "Error: No files successfully hashed",
                file=sys.stderr,
            )
            return 1

        print(f"  Successfully hashed {len(hashed_files)} files")

        # Step 4: Upload files
        print(f"\n[4/4] Uploading files to S3...")
        upload_result = upload_files_parallel(
            s3_client,
            hashed_files,
            bucket,
            prefix,
            args.threads,
            transfer_config,
        )

        # Print summary
        print_summary(
            upload_result,
            len(collected_files),
        )

        # Return appropriate exit code
        if upload_result["failed_files"]:
            print(
                "\nWarning: Some files failed to upload",
                file=sys.stderr,
            )
            return 1

        print("\nUpload completed successfully!")
        return 0

    except KeyboardInterrupt:
        print(
            "\n\nUpload cancelled by user",
            file=sys.stderr,
        )
        return 130
    except Exception as e:
        print(
            f"\nError: {e}",
            file=sys.stderr,
        )
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

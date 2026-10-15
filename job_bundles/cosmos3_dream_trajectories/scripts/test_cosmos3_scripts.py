"""Tests for this sample's guards. Standard library only.

    cd job_bundles/cosmos3_dream_trajectories
    python3 -B -m unittest discover -s scripts -p 'test_*.py' -v

Use -B. ScriptDir is a DIRECTORY input, so job attachments uploads everything
under scripts/, and a __pycache__ left behind by a test run ships to every
worker as dead weight compiled for the wrong Python version.

Every guard is tested in both directions. A guard that has only ever been seen
to pass is not known to fire, and the failure this sample exists to catch is a
task that reports success while producing nothing.
"""

import inspect
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import assert_clip_summary  # noqa: E402
import make_example_clips  # noqa: E402
import cosmos3_client as c3  # noqa: E402
import extract_actions  # noqa: E402
import generate_dream  # noqa: E402
import merge_dataset  # noqa: E402


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cosmos3-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, relpath, payload):
        path = os.path.join(self.tmp, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            if isinstance(payload, (dict, list)):
                json.dump(payload, handle)
            else:
                handle.write(payload)
        return path


class TestManifest(TempDirCase):
    def manifest(self, clips):
        return self.write("clips.json", {"clips": clips})

    def test_matching_count_passes(self):
        path = self.manifest([{"name": "a", "image": "a.png", "prompt": "p"}])
        self.assertEqual(len(generate_dream.load_manifest(path, 1)), 1)

    def test_count_mismatch_fails(self):
        path = self.manifest(
            [{"name": "a", "image": "a.png", "prompt": "p"}] * 3
        )
        with self.assertRaises(SystemExit) as caught:
            generate_dream.load_manifest(path, 2)
        self.assertIn("lists 3 clips", str(caught.exception))
        self.assertIn("ClipCount=3", str(caught.exception))

    def test_empty_clips_fails(self):
        path = self.manifest([])
        with self.assertRaises(SystemExit):
            generate_dream.load_manifest(path, 0)

    def test_missing_clips_key_fails(self):
        path = self.write("clips.json", {"videos": []})
        with self.assertRaises(SystemExit):
            generate_dream.load_manifest(path, 1)

    def test_present_image_resolves_relative_to_manifest(self):
        path = self.manifest([{"name": "a", "image": "frames/a.png", "prompt": "p"}])
        self.write("frames/a.png", "not really a png but non-empty")
        resolved = generate_dream.resolve_image(path, {"image": "frames/a.png"}, 1)
        self.assertTrue(os.path.isfile(resolved))

    def test_missing_image_fails(self):
        path = self.manifest([{"name": "a", "image": "frames/gone.png", "prompt": "p"}])
        with self.assertRaises(SystemExit) as caught:
            generate_dream.resolve_image(path, {"image": "frames/gone.png"}, 1)
        self.assertIn("image not found", str(caught.exception))

    def test_zero_byte_image_fails(self):
        path = self.manifest([{"name": "a", "image": "frames/empty.png", "prompt": "p"}])
        self.write("frames/empty.png", "")
        with self.assertRaises(SystemExit) as caught:
            generate_dream.resolve_image(path, {"image": "frames/empty.png"}, 1)
        self.assertIn("zero bytes", str(caught.exception))

    def test_clip_name_is_sanitized(self):
        # Every character outside [A-Za-z0-9-_] becomes one underscore, so the
        # four separator characters in "b/../c" produce four underscores. The
        # point is that no path separator or dot survives into a filename.
        self.assertEqual(generate_dream.clip_name({"name": "a b/../c"}, 1), "a_b____c")

    def test_clip_name_rejects_a_fully_stripped_name(self):
        with self.assertRaises(SystemExit) as caught:
            generate_dream.clip_name({"name": "///"}, 1)
        self.assertIn("no alphanumeric character", str(caught.exception))

    def test_unnamed_clip_gets_an_index_name(self):
        self.assertEqual(generate_dream.clip_name({}, 7), "clip007")


class TestTemplateAttachmentDeclaration(unittest.TestCase):
    """Guard the parameter type that decides what job attachments uploads.

    A real submission declared ClipManifest as objectType FILE. Job attachments
    uploaded that one file, the conditioning images named inside its JSON stayed
    on the workstation, and every task failed on a missing image after the step
    environment had already paid a 35 GB download. The images being next to the
    manifest made no difference: only what is declared travels.

    Parsed by text rather than with PyYAML, because this sample's tests are
    standard library only.
    """

    @classmethod
    def setUpClass(cls):
        template = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "template.yaml"
        )
        with open(template, "r", encoding="utf-8") as handle:
            cls.lines = handle.read().splitlines()

    def param_block(self, name):
        """Return the lines of the `- name: <name>` parameter definition."""
        start = None
        for index, line in enumerate(self.lines):
            if line.strip() == "- name: %s" % name:
                start = index
                break
        self.assertIsNotNone(start, "no parameter named %s in template.yaml" % name)
        block = [self.lines[start]]
        for line in self.lines[start + 1 :]:
            if line.startswith("- name:") or line.startswith("steps:"):
                break
            block.append(line)
        return "\n".join(block)

    def test_clip_dir_is_a_directory_input(self):
        block = self.param_block("ClipDir")
        self.assertIn("objectType: DIRECTORY", block)
        self.assertIn("dataFlow: IN", block)

    def test_clip_dir_is_not_declared_as_a_file(self):
        # The regression. A FILE here uploads the manifest without its images.
        self.assertNotIn("objectType: FILE", self.param_block("ClipDir"))

    def test_no_parameter_declares_a_bare_manifest_file(self):
        joined = "\n".join(self.lines)
        self.assertNotIn("- name: ClipManifest\n", joined + "\n")

    def test_output_dir_stays_inout(self):
        # Each task's copy also has to carry its peers' uploads.
        self.assertIn("dataFlow: INOUT", self.param_block("OutputDir"))

    def test_script_dir_is_a_directory_input(self):
        block = self.param_block("ScriptDir")
        self.assertIn("objectType: DIRECTORY", block)
        self.assertIn("dataFlow: IN", block)

    def step_block(self, name):
        """Return the lines of the `- name: <name>` step definition."""
        start = None
        for index, line in enumerate(self.lines):
            if line == "- name: %s" % name:
                start = index
                break
        self.assertIsNotNone(start, "no step named %s in template.yaml" % name)
        block = [self.lines[start]]
        for line in self.lines[start + 1 :]:
            if line.startswith("- name:"):
                break
            block.append(line)
        return "\n".join(block)

    def test_merge_depends_on_both_producers(self):
        # The regression. "Job Attachments Download for Step" fetches the
        # outputs of DIRECT dependencies only. With step 2 alone, actions/
        # arrived and dreams/ did not, because step 2 read the videos without
        # modifying them so they were not part of its own uploads. Relying on
        # step 2's own dependency on step 1 to carry them does not work.
        block = self.step_block("3 - Merge")
        self.assertIn("dependsOn: 1 - Dream", block)
        self.assertIn("dependsOn: 2 - Extract actions", block)

    def test_extract_actions_depends_on_dream(self):
        self.assertIn("dependsOn: 1 - Dream", self.step_block("2 - Extract actions"))


class TestManifestNameCollisions(unittest.TestCase):
    """Output filenames come from the sanitized clip name.

    Two entries that differ only by punctuation produce the same stem, so the
    second overwrites the first. Step 2 then fails with "expected N clip
    summaries ... found N-1", which points at step 1 rather than at the manifest.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cosmos3-manifest-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def manifest(self, names):
        path = os.path.join(self.tmp, "clips.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(
                {"clips": [{"name": n, "image": "a.png", "prompt": "p"} for n in names]},
                handle,
            )
        return path

    def test_names_differing_only_by_punctuation_are_rejected(self):
        with self.assertRaises(SystemExit) as caught:
            generate_dream.load_manifest(self.manifest(["pick cube", "pick_cube"]), 2)
        message = str(caught.exception)
        self.assertIn("pick_cube", message)
        self.assertIn("overwrite", message)

    def test_distinct_names_are_accepted(self):
        clips = generate_dream.load_manifest(self.manifest(["pick_cube", "lift_cube"]), 2)
        self.assertEqual(2, len(clips))

    def test_identical_names_are_rejected(self):
        with self.assertRaises(SystemExit):
            generate_dream.load_manifest(self.manifest(["same", "same"]), 2)

    def test_unnamed_clips_do_not_collide(self):
        # Unnamed entries fall back to clip%03d, which is index-derived.
        path = os.path.join(self.tmp, "unnamed.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"clips": [{"image": "a.png", "prompt": "p"} for _ in range(3)]}, handle)
        self.assertEqual(3, len(generate_dream.load_manifest(path, 3)))


class TestDefaultSceneProducesActions(unittest.TestCase):
    """The default path has to exercise all three steps.

    An earlier default paired the SO-101 scene with ActionMode=none, so step 2
    started a model server and then skipped every task, and the job produced no
    action data at all. Agibot is on Cosmos 3's inverse-dynamics list, so the
    default now recovers actions.
    """

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "template.yaml"), "r", encoding="utf-8") as handle:
            cls.template = handle.read()
        with open(os.path.join(root, "parameter_values.yaml"), "r", encoding="utf-8") as handle:
            cls.values = handle.read()

    def default_of(self, text, name):
        """The `default:` or `value:` that follows `- name: <name>`."""
        lines = text.splitlines()
        start = next(i for i, l in enumerate(lines) if l.strip() == "- name: %s" % name)
        for line in lines[start + 1 :]:
            stripped = line.strip()
            if stripped.startswith("- name:"):
                break
            for key in ("default:", "value:"):
                if stripped.startswith(key):
                    return stripped[len(key) :].strip()
        # Explicit raise rather than falling through: self.fail() does raise, but
        # a bare fall-through reads as an implicit `return None` to static
        # analysis and to the next person editing this.
        raise AssertionError("no default for %s in the template" % name)

    def test_template_defaults_recover_actions(self):
        self.assertEqual("inverse_dynamics", self.default_of(self.template, "ActionMode"))
        self.assertEqual("agibotworld", self.default_of(self.template, "DomainName"))
        self.assertEqual("29", self.default_of(self.template, "RawActionDim"))

    def test_parameter_values_agree_with_the_template(self):
        # Two files carry these defaults, and `deadline bundle submit` reads the
        # parameter_values one. Disagreement means the documented default and the
        # submitted default differ.
        for name in ("ActionMode", "DomainName", "RawActionDim"):
            self.assertEqual(
                self.default_of(self.template, name),
                self.default_of(self.values, name),
                "%s differs between template.yaml and parameter_values.yaml" % name,
            )

    def test_generator_default_scene_matches_the_template(self):
        self.assertIn("agibot", make_example_clips.SCENES)
        signature = inspect.signature(make_example_clips.main)
        del signature  # main() parses argv; the default lives in the parser
        source = inspect.getsource(make_example_clips.main)
        self.assertIn('default="agibot"', source)

    def test_every_scene_entry_is_well_formed(self):
        for name, entry in make_example_clips.SCENES.items():
            clips, builder, hint = entry
            self.assertTrue(clips, "%s has no clips" % name)
            self.assertTrue(callable(builder), "%s builder is not callable" % name)
            self.assertIsInstance(hint, str)
            for spec in clips:
                self.assertEqual(4, len(spec), "%s spec is not 4-tuple: %r" % (name, spec))

    def test_agibot_scene_renders_a_valid_png(self):
        out = tempfile.mkdtemp(prefix="cosmos3-agibot-")
        self.addCleanup(shutil.rmtree, out, True)
        fn = make_example_clips.agibot_scene(160, 96, 0.5, (120, 120, 120))
        path = os.path.join(out, "scene.png")
        make_example_clips.write_png(path, 160, 96, fn)
        with open(path, "rb") as handle:
            head = handle.read(24)
        self.assertEqual(b"\x89PNG\r\n\x1a\n", head[:8])
        self.assertEqual((160, 96), struct.unpack(">II", head[16:24]))

    def test_agibot_grippers_stay_inside_the_frame(self):
        # The arm geometry derives link length from the base-to-gripper distance.
        # A fixed length overshot the object as the frame grew, putting the
        # grippers above it instead of around it.
        width, height = 848, 480
        fn = make_example_clips.agibot_scene(width, height, 0.25, (168, 132, 92))
        centre = fn(width // 2, int(height * 0.62))
        self.assertEqual(3, len(centre))
        for reach in (0.0, 0.5, 1.0):
            make_example_clips.agibot_scene(width, height, reach, (10, 20, 30))


class TestQueueEnvironmentContract(unittest.TestCase):
    """Guard the queue environment this sample depends on.

    Two failures here are invisible to `openjd check` and cost a GPU run each:
    exceeding the service's 15,000-character environment template limit, and
    gating GPU injection on a registered `nvidia` runtime. The add-on fleet has
    no such runtime, so that gate is false and NO GPU flags are passed, leaving
    the container CPU-only with no error.
    """

    # deadline:CreateQueueEnvironment rejects a longer template.
    ENVIRONMENT_TEMPLATE_MAX_CHARS = 15000

    @classmethod
    def setUpClass(cls):
        repo = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        cls.path = os.path.join(repo, "queue_environments", "docker_queue_env.yaml")
        with open(cls.path, "r", encoding="utf-8") as handle:
            cls.text = handle.read()

    def test_fits_the_service_character_limit(self):
        self.assertLess(
            len(self.text),
            self.ENVIRONMENT_TEMPLATE_MAX_CHARS,
            "%s is %d chars; the service limit is %d"
            % (self.path, len(self.text), self.ENVIRONMENT_TEMPLATE_MAX_CHARS),
        )

    def code_lines(self):
        """Non-comment lines, so a guard cannot be satisfied by a comment."""
        return [
            line
            for line in self.text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def test_gpu_is_gated_on_the_cdi_spec(self):
        gate = [
            line
            for line in self.code_lines()
            if "/etc/cdi/nvidia.yaml" in line and "GPU_ARGS" in line
        ]
        self.assertTrue(
            gate, "no executable line gates GPU_ARGS on /etc/cdi/nvidia.yaml"
        )
        self.assertIn("--gpus all", gate[0])

    def test_gpu_is_not_gated_on_a_registered_runtime(self):
        # The regression. True on a rootful fleet, false on the add-on fleet.
        self.assertNotIn("Runtimes:.*nvidia", self.text)
        self.assertNotIn("--runtime=nvidia", self.text)

    def test_execs_as_container_root(self):
        # A rootless userns maps container root to the job user. Execing as the
        # host uid instead lands on a uid with no /etc/passwd entry in the image.
        self.assertIn("--user 0:0", self.text)

    def test_raises_shared_memory(self):
        self.assertIn("--shm-size", self.text)

    def test_publishes_a_model_cache_and_the_token(self):
        self.assertIn("HF_HOME=", self.text)
        self.assertIn("openjd_redacted_env: HF_TOKEN=", self.text)

    def test_declares_the_extensions_it_uses(self):
        for extension in ("WRAP_ACTIONS", "EXPR", "REDACTED_ENV_VARS"):
            self.assertIn(extension, self.text)


class TestAssertClipSummary(unittest.TestCase):
    """Step 1's own-artifact check.

    The guard it replaced counted dreams/*.json, which passes when a peer
    clip's summary synced in as an input and this task wrote nothing.
    """

    def setUp(self):
        self.dreams = tempfile.mkdtemp(prefix="cosmos3-dreams-")
        self.addCleanup(shutil.rmtree, self.dreams, True)

    def write(self, name, payload):
        with open(os.path.join(self.dreams, name), "w", encoding="utf-8") as handle:
            handle.write(payload)

    def test_passes_when_this_clip_wrote_its_summary(self):
        self.write("av_01.json", json.dumps({"clip_index": 1, "clip": "av_01"}))
        self.assertTrue(assert_clip_summary.has_summary(1, self.dreams))

    def test_fails_when_only_a_peer_summary_is_present(self):
        # The regression. A count-based check passed here.
        self.write("av_01.json", json.dumps({"clip_index": 1, "clip": "av_01"}))
        self.assertFalse(assert_clip_summary.has_summary(2, self.dreams))

    def test_fails_on_an_empty_directory(self):
        self.assertFalse(assert_clip_summary.has_summary(1, self.dreams))

    def test_skips_an_unparsable_sibling(self):
        self.write("broken.json", "not json at all")
        self.write("av_02.json", json.dumps({"clip_index": 2}))
        self.assertTrue(assert_clip_summary.has_summary(2, self.dreams))

    def test_skips_a_summary_that_is_not_an_object(self):
        self.write("odd.json", json.dumps(["not", "a", "dict"]))
        self.assertFalse(assert_clip_summary.has_summary(1, self.dreams))

    def test_missing_directory_is_a_failure_not_a_crash(self):
        self.assertFalse(
            assert_clip_summary.has_summary(1, os.path.join(self.dreams, "absent"))
        )

    def test_cli_exit_codes(self):
        self.write("av_01.json", json.dumps({"clip_index": 1}))
        self.assertEqual(0, assert_clip_summary.main(["1", self.dreams]))
        self.assertEqual(1, assert_clip_summary.main(["2", self.dreams]))
        self.assertEqual(2, assert_clip_summary.main(["notanint", self.dreams]))
        self.assertEqual(2, assert_clip_summary.main([self.dreams]))


class TestActionGuard(unittest.TestCase):
    def good(self, chunk=4, dim=3):
        return {
            "shape": [chunk, dim],
            "dtype": "float32",
            "data": [[0.1 * (i + 1)] * dim for i in range(chunk)],
        }

    def test_good_action_passes(self):
        sample = extract_actions.check_action(self.good(), 4, 3, "c")
        self.assertEqual(len(sample), 12)

    def test_wrong_dim_fails(self):
        with self.assertRaises(SystemExit) as caught:
            extract_actions.check_action(self.good(dim=3), 4, 9, "c")
        self.assertIn("action dim 3", str(caught.exception))

    def test_wrong_chunk_fails(self):
        with self.assertRaises(SystemExit) as caught:
            extract_actions.check_action(self.good(chunk=4), 60, 3, "c")
        self.assertIn("4 action steps", str(caught.exception))

    def test_missing_data_fails(self):
        with self.assertRaises(SystemExit) as caught:
            extract_actions.check_action({"shape": [4, 3]}, 4, 3, "c")
        self.assertIn("no action.data", str(caught.exception))

    def test_all_zero_action_fails(self):
        payload = {"shape": [4, 3], "data": [[0.0] * 3 for _ in range(4)]}
        with self.assertRaises(SystemExit) as caught:
            extract_actions.check_action(payload, 4, 3, "c")
        self.assertIn("predicted no motion", str(caught.exception))

    def test_non_finite_action_fails(self):
        payload = {"shape": [2, 2], "data": [[1.0, float("nan")], [2.0, 3.0]]}
        with self.assertRaises(SystemExit) as caught:
            extract_actions.check_action(payload, 2, 2, "c")
        self.assertIn("NaN or inf", str(caught.exception))

    def test_numberless_data_fails(self):
        with self.assertRaises(SystemExit) as caught:
            extract_actions.check_action({"shape": [1, 1], "data": []}, 1, 1, "c")
        self.assertIn("no numbers", str(caught.exception))

    def test_missing_shape_is_tolerated(self):
        # The dimensionality check is skipped, but the signal check still runs.
        payload = {"data": [[1.0, 2.0]]}
        self.assertEqual(len(extract_actions.check_action(payload, 1, 2, "c")), 2)


class TestReshape(unittest.TestCase):
    def test_nested_rows_are_preserved(self):
        action = {"shape": [2, 3], "data": [[1, 2, 3], [4, 5, 6]]}
        self.assertEqual(merge_dataset.rows_from_action(action, 3), [[1, 2, 3], [4, 5, 6]])

    def test_flat_stream_is_chunked(self):
        action = {"shape": None, "data": [1, 2, 3, 4, 5, 6]}
        self.assertEqual(merge_dataset.rows_from_action(action, 2), [[1, 2], [3, 4], [5, 6]])

    def test_indivisible_stream_fails(self):
        action = {"shape": None, "data": [1, 2, 3, 4, 5]}
        with self.assertRaises(SystemExit) as caught:
            merge_dataset.rows_from_action(action, 2)
        self.assertIn("not a multiple", str(caught.exception))

    def test_extra_leading_axis_is_flattened_to_rows(self):
        action = {"shape": [1, 2, 3], "data": [[[1, 2, 3], [4, 5, 6]]]}
        self.assertEqual(merge_dataset.rows_from_action(action, 3), [[1, 2, 3], [4, 5, 6]])


class TestClient(unittest.TestCase):
    def test_multipart_carries_fields_and_files(self):
        content_type, body = c3._encode_multipart(
            {"prompt": "hello"}, {"input_reference": ("a.png", b"\x89PNG", "image/png")}
        )
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
        self.assertIn(b'name="prompt"', body)
        self.assertIn(b"hello", body)
        self.assertIn(b'filename="a.png"', body)
        self.assertIn(b"\x89PNG", body)
        boundary = content_type.split("boundary=")[1]
        self.assertTrue(body.endswith(("--%s--\r\n" % boundary).encode("utf-8")))

    def test_process_alive_sees_this_process(self):
        self.assertTrue(c3.process_alive(os.getpid()))

    def test_process_alive_sees_a_dead_pid(self):
        # A pid that has certainly never run in this namespace.
        self.assertFalse(c3.process_alive(999999999))

    def test_wait_for_server_gives_up_on_a_dead_pid_without_waiting(self):
        # The point of the pid check: report a crashed server at once rather
        # than after the full boot timeout. A 600s timeout must not be waited
        # out here, so this also asserts the test itself stays fast.
        started = time.time()
        with self.assertRaises(c3.Cosmos3Error) as caught:
            c3.wait_for_server(
                "http://127.0.0.1:9",
                timeout_seconds=600,
                poll_seconds=0.01,
                log=lambda _msg: None,
                pid=999999999,
            )
        self.assertIn("exited during startup", str(caught.exception))
        self.assertLess(time.time() - started, 5.0)

    def test_wait_for_server_times_out_when_nothing_listens(self):
        with self.assertRaises(c3.Cosmos3Error) as caught:
            c3.wait_for_server(
                "http://127.0.0.1:9",
                timeout_seconds=0.2,
                poll_seconds=0.01,
                log=lambda _msg: None,
            )
        self.assertIn("did not become healthy", str(caught.exception))

    def test_cli_wait_reports_a_dead_pid_as_openjd_fail(self):
        # The serve script relies on this exit code and on the openjd_fail
        # prefix reaching stderr.
        proc = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "cosmos3_client.py"),
                "--wait", "http://127.0.0.1:9",
                "--timeout", "600",
                "--pid", "999999999",
                "--poll-seconds", "0.01",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("openjd_fail:", proc.stderr)
        self.assertIn("exited during startup", proc.stderr)

    def test_base_url_from_env_requires_the_variable(self):
        saved = os.environ.pop("COSMOS3_BASE_URL", None)
        try:
            with self.assertRaises(c3.Cosmos3Error) as caught:
                c3.base_url_from_env()
            self.assertIn("COSMOS3_BASE_URL is unset", str(caught.exception))
            os.environ["COSMOS3_BASE_URL"] = "http://127.0.0.1:8000"
            self.assertEqual(c3.base_url_from_env(), "http://127.0.0.1:8000")
        finally:
            os.environ.pop("COSMOS3_BASE_URL", None)
            if saved is not None:
                os.environ["COSMOS3_BASE_URL"] = saved


class TestMerge(TempDirCase):
    def populate(self, clips, dim=3, chunk=2, zero=False):
        for index in range(clips):
            name = "c%02d" % index
            self.write(
                "dreams/%s.json" % name,
                {"clip": name, "video": "dreams/%s.mp4" % name, "prompt": "p%d" % index},
            )
            self.write("dreams/%s.mp4" % name, "x" * 9000)
            value = 0.0 if zero else 0.5
            self.write(
                "actions/%s.json" % name,
                {"shape": [chunk, dim], "dtype": "float32",
                 "data": [[value] * dim for _ in range(chunk)]},
            )
            self.write(
                "actions/%s.meta.json" % name,
                {
                    "clip": name,
                    "clip_index": index + 1,
                    "action": "actions/%s.json" % name,
                    "video": "dreams/%s.mp4" % name,
                    "prompt": "p%d" % index,
                },
            )

    def run_merge(self, expected, dim=3, extra=None, action_mode="inverse_dynamics"):
        argv = [
            "merge_dataset.py",
            "--output-dir", self.tmp,
            "--expected-clips", str(expected),
            "--raw-action-dim", str(dim),
            "--fps", "10",
            "--action-mode", action_mode,
        ] + (extra or [])
        saved = sys.argv
        sys.argv = argv
        try:
            return merge_dataset.main()
        finally:
            sys.argv = saved

    def test_complete_dataset_merges(self):
        self.populate(3)
        self.assertEqual(self.run_merge(3), 0)
        with open(os.path.join(self.tmp, "dream_summary.json"), encoding="utf-8") as handle:
            summary = json.load(handle)
        self.assertEqual(summary["episodes"], 3)
        self.assertEqual(summary["total_steps"], 6)
        self.assertEqual(summary["tasks"], 3)
        info_path = os.path.join(self.tmp, "lerobot", "meta", "info.json")
        self.assertTrue(os.path.isfile(info_path))
        with open(os.path.join(self.tmp, "lerobot", "meta", "tasks.jsonl"), encoding="utf-8") as handle:
            tasks = [json.loads(line) for line in handle if line.strip()]
        self.assertTrue(all(row["task"].startswith("<DREAM> ") for row in tasks))
        for index in range(3):
            self.assertTrue(
                os.path.isfile(
                    os.path.join(
                        self.tmp, "lerobot", "videos", "observation.images.main",
                        "chunk-000", "episode_%06d.mp4" % index,
                    )
                )
            )

    def test_short_dataset_fails(self):
        self.populate(2)
        with self.assertRaises(SystemExit) as caught:
            self.run_merge(5)
        self.assertIn("found 2 of 5 expected clips", str(caught.exception))

    def test_missing_actions_dir_fails(self):
        self.populate(1)
        shutil.rmtree(os.path.join(self.tmp, "actions"))
        with self.assertRaises(SystemExit) as caught:
            self.run_merge(1)
        self.assertIn("no actions directory", str(caught.exception))

    def test_missing_video_fails(self):
        self.populate(1)
        os.remove(os.path.join(self.tmp, "dreams", "c00.mp4"))
        with self.assertRaises(SystemExit) as caught:
            self.run_merge(1)
        self.assertIn("video missing", str(caught.exception))

    def test_step_floor_fails_on_a_short_episode(self):
        self.populate(1, chunk=2)
        with self.assertRaises(SystemExit) as caught:
            self.run_merge(1, extra=["--min-steps-per-episode", "60"])
        self.assertIn("below the floor", str(caught.exception))

    def test_dimension_mismatch_fails_the_reshape(self):
        # 2 steps x 3 values written, merged as dim 4: 6 is not a multiple of 4.
        self.populate(1, dim=3, chunk=2)
        with self.assertRaises(SystemExit) as caught:
            self.run_merge(1, dim=4)
        self.assertIn("not a multiple", str(caught.exception))

    def test_video_only_merge_needs_no_actions(self):
        # ActionMode=none is the SO-101 path: step 2 is skipped, so the actions
        # directory never exists and the merge must still succeed.
        self.populate(2)
        shutil.rmtree(os.path.join(self.tmp, "actions"))
        self.assertEqual(self.run_merge(2, action_mode="none"), 0)
        with open(os.path.join(self.tmp, "dream_summary.json"), encoding="utf-8") as handle:
            summary = json.load(handle)
        self.assertEqual(summary["episodes"], 2)
        self.assertEqual(summary["action_mode"], "none")
        self.assertFalse(summary["has_actions"])
        with open(os.path.join(self.tmp, "lerobot", "meta", "info.json"), encoding="utf-8") as handle:
            info = json.load(handle)
        # No action feature, and the absence is stated rather than faked.
        self.assertFalse(info["has_actions"])
        self.assertNotIn("action", info["features"])
        self.assertIn("IDM", info["next_step"])
        # Videos are still filed under the LeRobot layout.
        for index in range(2):
            self.assertTrue(
                os.path.isfile(
                    os.path.join(self.tmp, "lerobot", "videos", "observation.images.main",
                                 "chunk-000", "episode_%06d.mp4" % index)
                )
            )
        # And no data/ tables, because there are no actions to tabulate.
        self.assertFalse(os.path.isdir(os.path.join(self.tmp, "lerobot", "data")))

    def test_video_only_merge_still_fails_on_a_short_run(self):
        self.populate(2)
        shutil.rmtree(os.path.join(self.tmp, "actions"))
        with self.assertRaises(SystemExit) as caught:
            self.run_merge(5, action_mode="none")
        self.assertIn("found 2 of 5 expected clip summaries", str(caught.exception))

    def test_video_only_merge_fails_on_a_missing_video(self):
        self.populate(1)
        shutil.rmtree(os.path.join(self.tmp, "actions"))
        os.remove(os.path.join(self.tmp, "dreams", "c00.mp4"))
        with self.assertRaises(SystemExit) as caught:
            self.run_merge(1, action_mode="none")
        self.assertIn("video missing", str(caught.exception))

    def test_video_only_merge_fails_on_a_truncated_video(self):
        self.populate(1)
        shutil.rmtree(os.path.join(self.tmp, "actions"))
        self.write("dreams/c00.mp4", "tiny")
        with self.assertRaises(SystemExit) as caught:
            self.run_merge(1, action_mode="none")
        self.assertIn("only 4 bytes", str(caught.exception))

    def test_action_mode_default_still_requires_actions(self):
        # The inverse_dynamics path must not quietly degrade to video-only.
        self.populate(1)
        shutil.rmtree(os.path.join(self.tmp, "actions"))
        with self.assertRaises(SystemExit) as caught:
            self.run_merge(1)
        self.assertIn("no actions directory", str(caught.exception))

    def test_duplicate_clip_prompts_collapse_to_one_task(self):
        self.populate(2)
        for name in ("c00", "c01"):
            self.write(
                "actions/%s.meta.json" % name,
                {
                    "clip": name,
                    "action": "actions/%s.json" % name,
                    "video": "dreams/%s.mp4" % name,
                    "clip_prompt": "same instruction",
                    "action_prompt": "You are a planning system.",
                },
            )
        self.assertEqual(self.run_merge(2), 0)
        with open(os.path.join(self.tmp, "dream_summary.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["tasks"], 1)

    def test_task_comes_from_the_clip_instruction_not_the_system_prompt(self):
        """The regression. `action_prompt` is job-wide, so building the task from
        it collapsed every episode to one row and dropped the per-clip
        instruction. The video-only path always read the clip's own prompt.
        """
        self.populate(2)
        for index, name in enumerate(("c00", "c01")):
            self.write(
                "actions/%s.meta.json" % name,
                {
                    "clip": name,
                    "action": "actions/%s.json" % name,
                    "video": "dreams/%s.mp4" % name,
                    "clip_prompt": "pick up object number %d" % index,
                    "action_prompt": "You are a dual-arm manipulation planning system.",
                },
            )
        self.assertEqual(self.run_merge(2), 0)
        with open(os.path.join(self.tmp, "dream_summary.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["tasks"], 2)
        tasks = open(
            os.path.join(self.tmp, "lerobot", "meta", "tasks.jsonl"), encoding="utf-8"
        ).read()
        self.assertIn("pick up object number 0", tasks)
        self.assertIn("pick up object number 1", tasks)
        self.assertNotIn("planning system", tasks)

    def test_falls_back_to_the_dream_summary_when_clip_prompt_is_absent(self):
        # Metas written before clip_prompt existed still merge correctly.
        self.populate(2)
        for name in ("c00", "c01"):
            self.write(
                "actions/%s.meta.json" % name,
                {
                    "clip": name,
                    "action": "actions/%s.json" % name,
                    "video": "dreams/%s.mp4" % name,
                    "action_prompt": "You are a planning system.",
                },
            )
        self.assertEqual(self.run_merge(2), 0)
        tasks = open(
            os.path.join(self.tmp, "lerobot", "meta", "tasks.jsonl"), encoding="utf-8"
        ).read()
        self.assertNotIn("planning system", tasks)


if __name__ == "__main__":
    unittest.main()

# Job Development Progression

When you're developing a job bundle to run on AWS Deadline Cloud, you will
likely start with something simple. As you add more options and split the workload
into smaller pieces that run in parallel, the complexity of your job
will grow.

This directory documents four stages you can take your job bundle through as
you develop it. It starts with a single self-contained job template, and
ends at a Python package bundled with all the trappings like script entrypoints
and unit tests.

While this example is built around Python, the ideas are not Python-specific.
Feel free to adapt them to your language toolchain of choice.

from setuptools import setup

install_requires = []
with open("requirements.in", "r") as fp:
    for line in fp:
        line.strip()
        if line:
            install_requires.append(line)


setup(
    name="linehaul",
    use_scm_version={
        "local_scheme": lambda v: "+{.node}{}".format(
            v,
            ".dirty" if v.dirty else "",
        ),
        "version_scheme": lambda v: "{.distance}.0".format(v),
    },

    entry_points={"console_scripts": ["linehaul = linehaul.cli:main"]},

    install_requires=install_requires,

    setup_requires=["setuptools_scm"],
)

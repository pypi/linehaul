from setuptools import setup, find_packages

install_requires = []
with open("requirements/main.in", "r") as fp:
    for line in fp:
        line.strip()
        if line:
            install_requires.append(line)


setup(
    name="linehaul",
    use_scm_version={
        "local_scheme": lambda v: "+{.node}{}".format(v, ".dirty" if v.dirty else ""),
        "version_scheme": lambda v: "3.{.distance}.0".format(v),
    },
    packages=find_packages(exclude=["tests*"]),
    package_data={"linehaul": ["schema.json"]},
    entry_points={"console_scripts": ["linehaul = linehaul.cli:cli"]},
    install_requires=install_requires,
    setup_requires=["setuptools_scm"],
)

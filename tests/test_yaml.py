import io

from rattler_build_conda_compat import yaml as rbcc_yaml
from ruamel.yaml import YAML


def test_yaml_dump_no_global_changes() -> None:
    data = {"value": "true"}

    for kind in ["global", "rbcc", "global", "rbcc"]:
        if kind == "global":
            yaml = YAML()
            sdata = io.StringIO()
            yaml.dump(data, sdata)
            assert sdata.getvalue() == "value: 'true'\n"
        else:
            yaml = rbcc_yaml._yaml_object()
            rbcc_sdata = io.StringIO()
            yaml.dump(data, rbcc_sdata)
            assert rbcc_sdata.getvalue() == "value: true\n"


def test_yaml_load_no_global_changes() -> None:
    sdata = "value: 0.02\n"

    for kind in ["global", "rbcc", "global", "rbcc"]:
        if kind == "global":
            yaml = YAML()
            data = yaml.load(sdata)
            assert data == {"value": 0.02}
        else:
            yaml = rbcc_yaml._yaml_object()
            rbcc_data = yaml.load(sdata)
            assert rbcc_data == {"value": "0.02"}

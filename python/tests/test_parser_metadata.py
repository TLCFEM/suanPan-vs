"""The shared parser reader reports object-tag ownership.

suanPan #410 moved tag extraction from most handlers into the dispatcher.
Groups were left untouched, so the registry value type is the reliable way
to tell the two layouts apart.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from suanpan_parser import (  # noqa: E402
    REGISTRY_FUNCTIONS,
    function_body,
    read_section_designations,
    registry_keywords,
    registry_tag_in_dispatcher,
)

DISPATCHER_OWNED = """\
int create_new_material(const shared_ptr<DomainBase>& domain, std::istringstream& command) {
    unsigned tag;
    if(!get_input(command, tag)) {
        suanpan_error("A valid tag is required.\\n");
        return SUANPAN_SUCCESS;
    }

    static const TokenRegistry<void (*)(unique_ptr<Material>&, std::istringstream&, unsigned)> registry{
        {"AFC", new_afc01},
        {"AFC01", new_afc01},
    };

    return SUANPAN_SUCCESS;
}
"""

HANDLER_OWNED = """\
int create_new_group(const shared_ptr<DomainBase>& domain, std::istringstream& command) {
    std::string group_type;
    if(!get_input(command, group_type)) return SUANPAN_SUCCESS;

    static const TokenRegistry<void (*)(unique_ptr<Group>&, std::istringstream&)> registry{
        {"NodeGroup", new_node_group},
    };

    return SUANPAN_SUCCESS;
}
"""

SOURCE = SCRIPTS.parent.parent / "suanPan"
EXPECTED = {
    category: category != "group" for category in REGISTRY_FUNCTIONS
}

COMMENTED_SOURCE = """\
// vec euisection(const std::string_view type) { return {}; }
/* a comment with a brace { and a "string" } */
vec euisection(const std::string_view type) {
    static const TokenRegistry<vec> registry{
        {"HEA100", {100.0, 8.0}}, // trailing comment
        {"IPE300", {300.0, 10.0, /* nested } */ 150.0}},
    };
    return {};
}
"""


def test_dispatcher_reads_tag():
    assert registry_tag_in_dispatcher(DISPATCHER_OWNED, "int create_new_material(")


def test_handler_reads_tag():
    assert not registry_tag_in_dispatcher(HANDLER_OWNED, "int create_new_group(")


def test_missing_dispatcher():
    assert not registry_tag_in_dispatcher("", "int create_new_material(")


def test_ignores_signatures_and_braces_in_comments_and_strings():
    body = function_body(COMMENTED_SOURCE, "vec euisection(")
    assert body.startswith("{")
    assert body.rstrip().endswith("}")
    assert registry_keywords(COMMENTED_SOURCE, "vec euisection(") == [
        "HEA100",
        "IPE300",
    ]


@pytest.mark.skipif(
    not (SOURCE / "Section/SectionParser.cpp").exists(),
    reason="suanPan checkout not available",
)
def test_reads_coded_section_designations():
    designations = read_section_designations(SOURCE)
    assert designations["containers"]["US2DA"] == [
        "usisection_adjusted",
        "usrhssection_adjusted",
        "uschssection_adjusted",
        "ustsection_adjusted",
    ]
    assert "IPE300" in designations["tables"]["euisection_adjusted"]
    # Only the adjusted US T-section table contains the extra WT shapes.
    assert "WT22X204" in designations["tables"]["ustsection_adjusted"]
    assert "WT22X204" not in designations["tables"]["ustsection"]


@pytest.mark.skipif(
    not (SOURCE / "Material/MaterialParser.cpp").exists(),
    reason="suanPan checkout not available",
)
def test_current_suanpan_layout():
    for category, expected in EXPECTED.items():
        relative, signature = REGISTRY_FUNCTIONS[category]
        text = (SOURCE / relative).read_text()
        assert registry_tag_in_dispatcher(text, signature) is expected, category

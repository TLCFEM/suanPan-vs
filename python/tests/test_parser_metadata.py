"""The shared parser reader reports object-tag ownership.

suanPan #410 moved tag extraction from most handlers into the dispatcher.
Sections and groups were left untouched, so the registry value type is the
reliable way to tell the two layouts apart.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from suanpan_parser import (  # noqa: E402
    REGISTRY_FUNCTIONS,
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
int create_new_section(const shared_ptr<DomainBase>& domain, std::istringstream& command) {
    std::string section_type;
    if(!get_input(command, section_type)) return SUANPAN_SUCCESS;

    static const TokenRegistry<void (*)(unique_ptr<Section>&, std::istringstream&)> registry{
        {"Box2D", new_box2d},
    };

    return SUANPAN_SUCCESS;
}
"""

SOURCE = SCRIPTS.parent.parent / "suanPan"
EXPECTED = {
    category: category not in {"group", "section"} for category in REGISTRY_FUNCTIONS
}


def test_dispatcher_reads_tag():
    assert registry_tag_in_dispatcher(DISPATCHER_OWNED, "int create_new_material(")


def test_handler_reads_tag():
    assert not registry_tag_in_dispatcher(HANDLER_OWNED, "int create_new_section(")


def test_missing_dispatcher():
    assert not registry_tag_in_dispatcher("", "int create_new_material(")


@pytest.mark.skipif(
    not (SOURCE / "Material/MaterialParser.cpp").exists(),
    reason="suanPan checkout not available",
)
def test_current_suanpan_layout():
    for category, expected in EXPECTED.items():
        relative, signature = REGISTRY_FUNCTIONS[category]
        text = (SOURCE / relative).read_text()
        assert registry_tag_in_dispatcher(text, signature) is expected, category

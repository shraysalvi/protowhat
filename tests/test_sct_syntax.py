import pytest

from tests.helper import state, dummy_checks
from protowhat.State import State
from protowhat.sct_syntax import (
    ExGen,
    Ex,
    state_dec_gen,
    get_checks_dict,
    create_sct_context,
    Chain,
    LazyChain,
    create_embed_state,
    create_embed_context,
    get_embed_chain_constructors,
)

state = pytest.fixture(state)
dummy_checks = pytest.fixture(dummy_checks)

state_dec = state_dec_gen(State, {})


@pytest.fixture
def addx():
    return lambda state, x: state + x


@pytest.fixture
def f():
    return LazyChain._from_func(lambda state, b: state + b, b="b")


@pytest.fixture
def f2():
    return LazyChain._from_func(lambda state, c: state + c, c="c")


def test_f_from_func(f):
    assert f("a") == "ab"


def test_f_sct_copy_kw(addx):
    assert LazyChain()._sct_copy(addx)(x="x")("state") == "statex"


def test_f_sct_copy_pos(addx):
    assert LazyChain()._sct_copy(addx)("x")("state") == "statex"


def test_ex_sct_copy_kw(addx):
    assert Ex("state")._sct_copy(addx)(x="x")._state == "statex"


def test_ex_sct_copy_pos(addx):
    assert Ex("state")._sct_copy(addx)("x")._state == "statex"


def test_f_2_funcs(f, addx):
    g = f._sct_copy(addx)

    assert g(x="x")("a") == "abx"


def test_f_add_unary_func(f):
    g = f >> (lambda state: state + "c")
    assert g("a") == "abc"


def test_f_add_f(f, f2):
    g = f >> f2
    assert g("a") == "abc"


def test_f_from_state_dec(addx):
    dec_addx = state_dec(addx)
    f = dec_addx(x="x")
    isinstance(f, LazyChain)
    assert f("state") == "statex"


@pytest.fixture
def ex():
    return Ex("state")._sct_copy(lambda state, x: state + x)("x")


def test_ex_add_f(ex, f):
    (ex >> f)._state = "statexb"


def test_ex_add_unary(ex):
    assert (ex >> (lambda state: state + "b"))._state == "statexb"


def test_ex_add_ex_err(ex):
    with pytest.raises(BaseException):
        ex >> ex


def test_f_add_ex_err(f, ex):
    with pytest.raises(BaseException):
        f >> ex


def test_state_dec_instant_eval(state):
    @state_dec
    def stu_code(state, x="x"):
        return state.student_code + x

    assert stu_code(state) == "student_codex"


def test_get_checks_dict_package():
    # Given
    from protowhat import checks

    # When
    sct_dict = get_checks_dict(checks)

    # Then
    assert isinstance(sct_dict, dict)
    assert sct_dict == {
        str(sct.__name__): sct
        for sct in [checks.get_bash_history, checks.update_bash_history_info]
    }  # other checks not exported in init


def test_get_checks_dict_module():
    # Given
    from protowhat.checks import check_simple

    # When
    sct_dict = get_checks_dict(check_simple)

    # Then
    assert len(sct_dict) == 3
    assert sct_dict["has_chosen"] == check_simple.has_chosen
    assert sct_dict["success_msg"] == check_simple.success_msg


def test_create_sct_context(state, dummy_checks):
    # When
    sct_ctx = create_sct_context(State, dummy_checks, state)

    # Then
    assert "state_dec" in sct_ctx

    for check in dummy_checks:
        assert check in sct_ctx
        assert callable(sct_ctx[check])

    for chain in ["Ex", "F"]:
        assert chain in sct_ctx
        assert isinstance(sct_ctx[chain](), Chain)
        for check in dummy_checks:
            assert getattr(sct_ctx[chain](), check)


def test_create_embed_state(state):
    # Given
    state.debug = True
    assert state.solution_result == {}

    class XState(State):
        def __init__(self, *args, custom=None, **kwargs):
            super().__init__(*args, **kwargs)
            self.custom = custom

    def derive_custom_state_args(parent_state):
        assert parent_state == state
        return {"student_code": "override", "custom": "Xstate property"}

    # When
    embed_state = create_embed_state(
        XState, state, derive_custom_state_args, {"test": "nonsense highlight"},
    )

    # Then
    assert isinstance(embed_state, XState)
    assert not hasattr(embed_state, "debug")  # TODO
    assert embed_state.student_code == "override"
    assert embed_state.custom == "Xstate property"
    assert embed_state.reporter.runner == state.reporter
    assert embed_state.reporter.highlight_offset == {"test": "nonsense highlight"}
    assert embed_state.creator == {"type": "embed", "args": {"state": state}}


def test_create_embed_context(state, dummy_checks):
    # Given
    Ex = ExGen(state, dummy_checks)
    assert Ex()._state == state

    def derive_custom_state_args(parent_state):
        assert parent_state == state
        return {"student_code": "override"}

    # When
    embed_context = create_embed_context(
        "proto", Ex(), derive_custom_state_args=derive_custom_state_args,
    )

    # Then
    assert isinstance(embed_context["get_bash_history"](), Chain)
    assert isinstance(embed_context["F"]().get_bash_history(), Chain)

    embed_state = embed_context["Ex"].root_state
    assert isinstance(embed_state, State)
    assert embed_state.student_code == "override"
    assert embed_state.reporter.runner == state.reporter
    assert embed_state.creator == {"type": "embed", "args": {"state": state}}


def test_get_embed_chain_constructors(state, dummy_checks):
    # Given
    Ex = ExGen(state, dummy_checks)
    assert Ex()._state == state

    # When
    EmbedEx, EmbedF = get_embed_chain_constructors("proto", Ex())

    # Then
    assert isinstance(EmbedEx(), Chain)
    assert isinstance(EmbedF(), Chain)


def test_state_linking_root_creator(state):
    def diagnose(end_state):
        assert end_state.creator is None

    f = LazyChain(attr_scts={"diagnose": diagnose})
    Ex(state) >> f.diagnose()


def test_state_linking_root_creator_noop(state, dummy_checks):
    def diagnose(end_state):
        assert end_state.creator is None

    TestEx = ExGen(state, dummy_checks)
    TestEx().noop() >> LazyChain(attr_scts={"diagnose": diagnose}).diagnose()


def test_state_linking_root_creator_child_state(state, dummy_checks):
    def diagnose(end_state):
        assert end_state != state
        assert end_state.parent_state is state
        assert len(end_state.state_history) == 2
        assert state == end_state.state_history[0]
        assert end_state == end_state.state_history[1]

    TestEx = ExGen(state, dummy_checks)
    TestEx().child_state() >> LazyChain(attr_scts={"diagnose": diagnose}).diagnose()

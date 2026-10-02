import sys, os
sys.path.insert(0, os.environ.get("TT_SOLVER_DIR", "."))
import pytest
solver = pytest.importorskip("solver")
import solver_ui as ui
BOARD = "? "*18 + "2 A 3 7 9 J 5 3 9 3"
def test_flow():
    s = ui.new_session(BOARD, "K", 23)
    assert "Ready" in ui.status(s) or "Draw" in ui.status(s)
    assert "position" in ui.recommend(s, 50, 1).lower()
    ui.do_draw(s, "4"); assert s.game.waste == "4" and s.game.stock_remaining == 22
    ui.do_draw(s, "2")
    s.undo(); assert s.game.waste == "4"
def test_bad_board_len():
    with pytest.raises(ValueError): ui.parse_board("A 2 3")
def test_render_has_28():
    assert ui.render_board(ui.new_session(BOARD, "K", 23)).count('class="c ') == 28

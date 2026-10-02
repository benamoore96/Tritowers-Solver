import os
import gradio as gr
import solver_ui as ui
from tritowers_vision import extract_screen, recognize
from tritowers_vision.calibrated import read
from tritowers_vision.rank import load_templates
TEMPLATES = load_templates(os.environ["TT_TEMPLATES"]) if os.environ.get("TT_TEMPLATES") and os.path.exists(os.environ["TT_TEMPLATES"]) else []
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def parse_corners(text):
    if not text or not text.strip(): return None
    nums = [float(x) for x in text.replace(";", ",").replace("\n", ",").split(",") if x.strip()]
    if len(nums) != 8: raise gr.Error("Corners: 8 numbers, x,y for 4 corners")
    return [(nums[i], nums[i + 1]) for i in range(0, 8, 2)]

def draft_to_board_text(draft):
    """Unknowns stay '?'; nothing is guessed. Empty slots become '--'."""
    tokens = []
    for i in range(1, 29):
        c = draft["cards"][f"tableau-{i:02d}"]
        tokens.append("--" if c["state"] == "empty" else (c["rank"] or "?"))
    return " ".join(tokens), (draft["cards"]["waste"]["rank"] or "")

def inspect_image(path, corners_text):
    if not path: return None, None, {"unsupported_reason": "no_image"}, {}, "", "", "Upload an image first."
    ex = extract_screen(path, parse_corners(corners_text))
    result = recognize(ex.rectified, ex.corners, ex.manual).to_dict()
    if ex.rectified is None or not TEMPLATES:
        return ex.overlay, ex.rectified, result, {"note": "Calibrated pass unavailable: no rectified screen or no templates (set TT_TEMPLATES)."}, "", "", "No draft."
    d = read(ex.rectified, TEMPLATES); board, waste = draft_to_board_text(d)
    msg = ("Review needed on: " + ", ".join(d["needs_human_review"]) if d["needs_human_review"] else "No flagged slots") + ". Suit is not read; stock counter is not read - enter it yourself (HUD may show engine stock + 1; unverified)."
    return ex.overlay, ex.rectified, result, d, board, waste, msg

def start(board, waste, stock):
    if not (waste or "").strip(): raise gr.Error("Choose the waste card before starting.")
    try: s = ui.new_session(board, waste.strip(), stock)
    except Exception as e: raise gr.Error(str(e))
    return s, ui.render_board(s), ui.status(s), "", ""

def act(fn):
    def run(s, *args):
        if s is None: raise gr.Error("Start a game first.")
        try: out = fn(s, *args)
        except Exception as e: raise gr.Error(str(e))
        return s, ui.render_board(s), ui.status(s), out or "", "\n".join(s.log[-8:])
    return run
rec = act(lambda s, n, seed: ui.recommend(s, n, seed)); play = act(lambda s, p: ui.do_play(s, p)); reveal = act(lambda s, p, r: ui.do_reveal(s, p, r))
draw = act(lambda s, r: ui.do_draw(s, r)); undo = act(lambda s: s.undo())

with gr.Blocks(title="TriTowers") as demo:
    gr.Markdown("# TriTowers\nRank-only solver with a photo reader. Recognition is a one-skin prototype: always check its draft. Sampled percentages are estimates, never proofs.")
    session = gr.State(None)
    with gr.Tab("Solver"):
        with gr.Row():
            with gr.Column(scale=1):
                board = gr.Textbox(label="Board, positions 1-28 (A 2-10 J Q K, ? covered, -- empty)", lines=3, value="? " * 18 + "2 A 3 7 9 J 5 3 9 3")
                with gr.Row(): waste = gr.Dropdown(RANKS, label="Waste card (required)", value=None, allow_custom_value=True); stock = gr.Number(label="Stock cards left (engine count)", value=23, precision=0)
                begin = gr.Button("Start game", variant="primary")
            with gr.Column(scale=2):
                view = gr.HTML(); state_line = gr.Markdown(); advice = gr.Markdown()
                with gr.Row(): sims = gr.Slider(100, 5000, value=1200, step=100, label="Simulations"); seed = gr.Textbox(label="Seed (optional)")
                ask = gr.Button("Recommend a move", variant="primary")
                with gr.Row(): pos = gr.Number(label="Position", precision=0); do_play_btn = gr.Button("Play it"); undo_btn = gr.Button("Undo")
                with gr.Row(): rpos = gr.Number(label="Reveal position", precision=0); rrank = gr.Dropdown(RANKS, label="Rank", allow_custom_value=True); rbtn = gr.Button("Reveal")
                with gr.Row(): drank = gr.Dropdown(RANKS, label="Card drawn from stock", allow_custom_value=True); dbtn = gr.Button("Draw")
                history = gr.Textbox(label="Log", lines=4, interactive=False)
        outs = [session, view, state_line, advice, history]
        begin.click(start, [board, waste, stock], outs); ask.click(rec, [session, sims, seed], outs); do_play_btn.click(play, [session, pos], outs)
        rbtn.click(reveal, [session, rpos, rrank], outs); dbtn.click(draw, [session, drank], outs); undo_btn.click(undo, [session], outs)
    with gr.Tab("Photo to board"):
        upload = gr.Image(type="filepath", label="Quiz-machine photo or screenshot")
        corners = gr.Textbox(label="Optional manual screen corners (x,y x4); 0,0,W,0,W,H,0,H for an already-cropped screen")
        go = gr.Button("Read photo", variant="primary"); note = gr.Markdown()
        with gr.Row(): overlay = gr.Image(label="Detected screen"); rectified = gr.Image(label="Rectified screen")
        pboard = gr.Textbox(label="Draft board (edit before use)", lines=3); pwaste = gr.Textbox(label="Draft waste")
        with gr.Accordion("Raw recognition output", open=False): result = gr.JSON(); draft = gr.JSON()
        go.click(inspect_image, [upload, corners], [overlay, rectified, result, draft, pboard, pwaste, note])
        send = gr.Button("Copy draft to Solver tab"); send.click(lambda b, w: (b, w), [pboard, pwaste], [board, waste])
if __name__ == "__main__": demo.launch()

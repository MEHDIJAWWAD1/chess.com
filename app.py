import os
import random
import shutil

import streamlit as st
import chess
import chess.engine

# --- PAGE CONFIG ---
st.set_page_config(page_title="Streamlit Interactive Chess Bot", layout="wide")
st.title("♟️ Streamlit Interactive Chess Bot & Analyzer")

# --- PATH TO YOUR STOCKFISH BINARY ---
STOCKFISH_PATH = (
    os.getenv("STOCKFISH_PATH")
    or shutil.which("stockfish")
    or r"C:\Users\mehdi\Downloads\stockfish-windows-x86-64-universal\stockfish\stockfish-windows-x86-64-universal.exe"
)

# --- INITIALIZE SESSION STATE ---
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "game_over" not in st.session_state:
    st.session_state.game_over = False
if "move_history" not in st.session_state:
    st.session_state.move_history = []  # Stores (FEN, move)
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "selected_square" not in st.session_state:
    st.session_state.selected_square = None
if "estimated_elo" not in st.session_state:
    st.session_state.estimated_elo = None

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("Settings")

difficulty_levels = {
    "Beginner (Elo ~800)": {"skill": 0, "depth": 2, "time": 0.1},
    "Casual (Elo ~1200)": {"skill": 5, "depth": 5, "time": 0.2},
    "Intermediate (Elo ~1600)": {"skill": 10, "depth": 8, "time": 0.5},
    "Advanced (Elo ~2000)": {"skill": 15, "depth": 12, "time": 1.0},
    "Maximum (Elo 3000+)": {"skill": 20, "depth": 15, "time": 2.0}
}

selected_diff = st.sidebar.selectbox("Choose Bot Difficulty:", list(difficulty_levels.keys()))
bot_config = difficulty_levels[selected_diff]

if st.sidebar.button("Reset Game"):
    st.session_state.board = chess.Board()
    st.session_state.game_over = False
    st.session_state.move_history = []
    st.session_state.analysis_results = None
    st.session_state.estimated_elo = None
    st.session_state.selected_square = None
    st.rerun()

# --- BOT MOVE LOGIC ---
def get_bot_move():
    legal_moves = list(st.session_state.board.legal_moves)
    if not legal_moves:
        return None

    if os.path.isfile(STOCKFISH_PATH):
        try:
            with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
                engine.configure({"Skill Level": bot_config["skill"]})
                result = engine.play(
                    st.session_state.board,
                    chess.engine.Limit(
                        time=bot_config["time"],
                        depth=bot_config["depth"],
                    ),
                )
                if result.move is not None:
                    return result.move
        except Exception as exc:
            st.warning(f"Stockfish could not start ({exc}). The bot will use a basic legal-move fallback.")
    else:
        st.warning(
            "Stockfish was not found. Set the STOCKFISH_PATH environment variable "
            "to its executable; using a basic legal-move fallback for now."
        )

    return random.choice(legal_moves)


def analyze_game(engine):
    classifications = {
        "Brilliant ✨": 0,
        "Great Move 🌟": 0,
        "Best Move ✅": 0,
        "Excellent 🟩": 0,
        "Inaccuracy 🟨": 0,
        "Mistake 🟧": 0,
        "Blunder 🟥": 0,
    }
    analysis_report = []
    centipawn_losses = []
    replay_board = chess.Board()

    for idx, (_, move) in enumerate(st.session_state.move_history):
        if move not in replay_board.legal_moves:
            raise ValueError(
                f"Saved move {idx + 1} ({move.uci()}) is illegal when replaying the game. "
                "Reset the game and play a new one before analyzing."
            )

        move_san = replay_board.san(move)
        if idx % 2 == 0:
            info_before = engine.analyse(replay_board, chess.engine.Limit(depth=12))
            score_before = info_before["score"].white().score(mate_score=10000)
            best_engine_move = info_before.get("pv", [None])[0]

        replay_board.push(move)

        if idx % 2 == 0:
            info_after = engine.analyse(replay_board, chess.engine.Limit(depth=12))
            score_after = info_after["score"].white().score(mate_score=10000)
            score_change = (score_after - score_before) / 100.0
            centipawn_losses.append(max(0, -score_after + score_before))

            if move == best_engine_move:
                label = "Best Move ✅"
            elif score_change >= -0.2:
                label = "Excellent 🟩"
            elif score_change >= -0.5:
                label = "Inaccuracy 🟨"
            elif score_change >= -1.5:
                label = "Mistake 🟧"
            else:
                label = "Blunder 🟥"

            classifications[label] += 1
            analysis_report.append({
                "Move Num": (idx // 2) + 1,
                "Move": move_san,
                "Rating": label,
                "Score Change": round(score_change, 2),
            })

    average_loss = sum(centipawn_losses) / len(centipawn_losses) if centipawn_losses else 0
    estimated_elo = max(
        600,
        min(2800, round((2800 - 1000 * (average_loss / 100) ** 0.5) / 10) * 10),
    )
    return {
        "summary": classifications,
        "details": analysis_report,
        "average_loss": average_loss,
        "estimated_elo": estimated_elo,
    }


# Recover a bot turn left pending by an earlier engine failure.
if st.session_state.board.turn == chess.BLACK and not st.session_state.board.is_game_over():
    pending_bot_move = get_bot_move()
    if pending_bot_move is not None and pending_bot_move in st.session_state.board.legal_moves:
        st.session_state.move_history.append((st.session_state.board.fen(), pending_bot_move))
        st.session_state.board.push(pending_bot_move)
        st.session_state.analysis_results = None
        st.session_state.estimated_elo = None

# Check game over status, showing checkmate before the general check notice.
if st.session_state.board.is_checkmate():
    st.session_state.game_over = True
    winner = "Black" if st.session_state.board.turn == chess.WHITE else "White"
    st.success(f"Checkmate! {winner} wins.")
elif st.session_state.board.is_game_over():
    st.session_state.game_over = True
    outcome = st.session_state.board.outcome()
    st.success(f"Game Over! Result: {outcome.result()} ({outcome.termination.name})")
elif st.session_state.board.is_check():
    checked_side = "White" if st.session_state.board.turn == chess.WHITE else "Black"
    st.warning(f"Check! {checked_side} is in check.")

# --- MAIN LAYOUT ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Interactive Board")

    board = st.session_state.board
    piece_symbols = {
        chess.Piece(chess.KING, chess.WHITE): "♔",
        chess.Piece(chess.QUEEN, chess.WHITE): "♕",
        chess.Piece(chess.ROOK, chess.WHITE): "♖",
        chess.Piece(chess.BISHOP, chess.WHITE): "♗",
        chess.Piece(chess.KNIGHT, chess.WHITE): "♘",
        chess.Piece(chess.PAWN, chess.WHITE): "♙",
        chess.Piece(chess.KING, chess.BLACK): "♚",
        chess.Piece(chess.QUEEN, chess.BLACK): "♛",
        chess.Piece(chess.ROOK, chess.BLACK): "♜",
        chess.Piece(chess.BISHOP, chess.BLACK): "♝",
        chess.Piece(chess.KNIGHT, chess.BLACK): "♞",
        chess.Piece(chess.PAWN, chess.BLACK): "♟",
    }

    selected_square = st.session_state.selected_square
    legal_targets = (
        {
            move.to_square
            for move in board.legal_moves
            if move.from_square == selected_square
        }
        if selected_square is not None
        else set()
    )

    for rank in range(7, -1, -1):
        squares = st.columns(8)
        for file in range(8):
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            if piece:
                label = piece_symbols[piece]
                if square in legal_targets:
                    label = f"{label}\n●"
            else:
                label = "•" if square in legal_targets else " "
            selected = square == st.session_state.selected_square
            disabled = st.session_state.game_over or board.turn != chess.WHITE

            if squares[file].button(
                label,
                key=f"square_{square}",
                type="primary" if selected else "secondary",
                disabled=disabled,
                use_container_width=True,
            ):
                selected_square = st.session_state.selected_square
                if selected_square is None:
                    if piece and piece.color == chess.WHITE:
                        st.session_state.selected_square = square
                        st.rerun()
                elif square == selected_square:
                    st.session_state.selected_square = None
                    st.rerun()
                else:
                    candidate_moves = [
                        move for move in board.legal_moves
                        if move.from_square == selected_square and move.to_square == square
                    ]
                    if candidate_moves:
                        move = next(
                            (candidate for candidate in candidate_moves if candidate.promotion == chess.QUEEN),
                            candidate_moves[0],
                        )
                        st.session_state.move_history.append((board.fen(), move))
                        board.push(move)
                        st.session_state.analysis_results = None
                        st.session_state.estimated_elo = None
                        st.session_state.selected_square = None

                        if board.is_game_over():
                            st.session_state.game_over = True
                        else:
                            bot_move = get_bot_move()
                            if bot_move is None or bot_move not in board.legal_moves:
                                st.error("The bot could not find a legal move. Reset the game and try again.")
                            else:
                                st.session_state.move_history.append((board.fen(), bot_move))
                                board.push(bot_move)
                                if board.is_game_over():
                                    st.session_state.game_over = True
                        st.rerun()
                    else:
                        target_piece = board.piece_at(square)
                        st.session_state.selected_square = (
                            square if target_piece and target_piece.color == chess.WHITE else None
                        )
                        st.rerun()

with col2:
    st.subheader("Move History")
    moves_san = []
    for fen, move in st.session_state.move_history:
        # Reconstruct the SAN names for display
        temp_b = chess.Board(fen)
        moves_san.append(temp_b.san(move))
        
    formatted_history = []
    for i in range(0, len(moves_san), 2):
        turn_str = f"{(i//2)+1}. {moves_san[i]}"
        if i + 1 < len(moves_san):
            turn_str += f"   {moves_san[i+1]}"
        formatted_history.append(turn_str)
        
    st.text_area("Moves Played", value="\n".join(formatted_history), height=380, disabled=True)

# --- POST-GAME AI ANALYSIS SECTION ---
st.write("---")
st.subheader("📊 Post-Game AI Analysis")

if not st.session_state.game_over:
    st.info("Complete the game or click below to run an evaluation on the current board state.")

analysis_col, elo_col = st.columns(2)
analyze_clicked = analysis_col.button("Analyze Game Moves")
estimate_elo_clicked = elo_col.button("Estimate My Elo")

if analyze_clicked or estimate_elo_clicked:
    if not st.session_state.move_history:
        st.warning("No moves have been played yet!")
    elif not os.path.isfile(STOCKFISH_PATH):
        st.error(
            "Stockfish is required for analysis and an Elo estimate. Set STOCKFISH_PATH "
            "to the full path of your Stockfish executable."
        )
    else:
        with st.spinner("Analyzing your moves..."):
            try:
                with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
                    st.session_state.analysis_results = analyze_game(engine)
                    if estimate_elo_clicked:
                        st.session_state.estimated_elo = st.session_state.analysis_results["estimated_elo"]
            except Exception as e:
                st.error(f"Analysis engine error: {e}")

if st.session_state.estimated_elo is not None:
    st.metric("Estimated Elo (rough)", st.session_state.estimated_elo)
    st.caption(
        "This is only a rough estimate from your average centipawn loss, not an official rating. "
        "It becomes more meaningful after several games."
    )

if st.session_state.analysis_results:
    res = st.session_state.analysis_results
    st.markdown("### Move Breakdown Summary")
    metrics_cols = st.columns(len(res["summary"]))
    for col, (label, count) in zip(metrics_cols, res["summary"].items()):
        col.metric(label, count)
        
    st.markdown("### Step-by-Step Breakdown")
    st.table(res["details"])

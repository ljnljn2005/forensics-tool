import os, sys, subprocess, threading
import matplotlib
matplotlib.use("Agg")
import customtkinter as ctk
from tkinter import filedialog, messagebox
from queue import Queue, Empty
from typing import Optional

path_os = os.path
GAPS_ROOT = path_os.join(path_os.dirname(path_os.abspath(__file__)), "gaps-main")
OUTPUT_DIR = path_os.join(path_os.dirname(path_os.abspath(__file__)), "10086")

DEFAULT_PIECE_SIZE = 64
DEFAULT_GENERATIONS = 20
DEFAULT_POPULATION = 200
MIN_PIECE_SIZE = 32
MAX_PIECE_SIZE = 128

_gaps_cmd_cache: Optional[str] = None
_gaps_cmd_lock = threading.Lock()


def _get_gaps_cmd() -> Optional[str]:
    global _gaps_cmd_cache
    with _gaps_cmd_lock:
        if _gaps_cmd_cache is not None:
            return _gaps_cmd_cache
        for cmd in ["gaps", "gaps.exe"]:
            try:
                subprocess.run([cmd, "--help"], capture_output=True, timeout=5)
                _gaps_cmd_cache = cmd
                return cmd
            except Exception:
                pass
        _gaps_cmd_cache = ""
        return ""

def _is_piece_size_valid(image_path, piece_size):
    from PIL import Image
    img = Image.open(image_path)
    w, h = img.size
    return w % piece_size == 0 and h % piece_size == 0

def _get_image_dimensions(image_path):
    from PIL import Image
    img = Image.open(image_path)
    return img.size

def _find_common_divisors(w, h, lo=MIN_PIECE_SIZE, hi=MAX_PIECE_SIZE):
    result = []
    for d in range(lo, min(w, h, hi) + 1):
        if w % d == 0 and h % d == 0:
            result.append(d)
    return result

def _suggest_auto_config(w, h):
    divisors = _find_common_divisors(w, h)
    best, best_score = None, float("inf")
    alternatives = []
    for d in divisors:
        cols, rows = w // d, h // d
        total = cols * rows
        score = abs(total - 200)
        entry = (d, cols, rows, total)
        if score < best_score:
            best_score, best = score, entry
        alternatives.append(entry)
    return (best, alternatives) if best else (None, [])

def _resize_for_puzzle(src_path, piece_size):
    from PIL import Image
    img = Image.open(src_path)
    w, h = img.size
    nw, nh = (w // piece_size) * piece_size, (h // piece_size) * piece_size
    if (nw, nh) == (w, h):
        return src_path
    resized = img.resize((nw, nh), Image.LANCZOS)
    base, ext = os.path.splitext(src_path)
    out = base + "_adapted" + ext
    resized.save(out)
    return out

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class GapsGUICTk(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gaps 拼图工具")
        self.geometry("900x700")
        self.minsize(720, 520)

        self.src_path: Optional[str] = None
        self.puzzle_path: Optional[str] = None
        self._running = False
        self._cancel_flag = False
        self._process: Optional[subprocess.Popen] = None
        self._msg_queue = Queue()
        self._thread: Optional[threading.Thread] = None

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # ---- sidebar ----
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color="#1c1c1e")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="Gaps 拼图", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#ffffff").pack(pady=(20, 0), padx=16, anchor="w")
        ctk.CTkLabel(self.sidebar, text="遗传算法 · 自动还原",
                     font=ctk.CTkFont(size=11), text_color="#8e8e93").pack(pady=(4, 20), padx=16, anchor="w")

        self.nav_btns = {}
        for key, text in [("create","生成拼图"), ("solve","还原拼图"), ("params","参数设置"), ("log","运行日志")]:
            btn = ctk.CTkButton(self.sidebar, text=text, fg_color="transparent",
                                anchor="w", font=ctk.CTkFont(size=13),
                                hover_color="#2c2c2e", corner_radius=6,
                                command=lambda k=key: self._switch_page(k))
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_btns[key] = btn

        self.status_label = ctk.CTkLabel(self.sidebar, text="就绪", font=ctk.CTkFont(size=10),
                                          text_color="#8e8e93")
        self.status_label.pack(side="bottom", pady=12)

        # ---- content area ----
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.pack(side="left", fill="both", expand=True)

        self.pages = {}
        self.pages["create"] = self._build_create_page()
        self.pages["solve"]  = self._build_solve_page()
        self.pages["params"] = self._build_params_page()
        self.pages["log"]    = self._build_log_page()

        self._switch_page("create")
        self._poll_queue()

    def _switch_page(self, key):
        for k, btn in self.nav_btns.items():
            if k == key:
                btn.configure(fg_color="#007aff", hover_color="#007aff", text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", hover_color="#2c2c2e", text_color="#d1d1d6")
        for p in self.pages.values():
            p.pack_forget()
        self.pages[key].pack(fill="both", expand=True, padx=16, pady=16)

    # ==================== CREATE ====================
    def _build_create_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="生成打乱拼图", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="both", expand=True)

        r1 = ctk.CTkFrame(card, fg_color="transparent")
        r1.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkButton(r1, text="选择原图", font=ctk.CTkFont(size=13),
                      command=self._choose_src).pack(side="left", padx=(0, 8))
        self.src_label = ctk.CTkLabel(r1, text="尚未选择", font=ctk.CTkFont(size=12),
                                       text_color="#6e6e73")
        self.src_label.pack(side="left")

        r1b = ctk.CTkFrame(card, fg_color="transparent")
        r1b.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(r1b, text="智能适配", command=self._auto_adapt,
                      fg_color="#34c759", hover_color="#2da94d", height=36).pack(side="left", padx=(0, 8))
        self.create_btn = ctk.CTkButton(r1b, text="生成拼图", command=self._create_puzzle,
                                         fg_color="#007aff", hover_color="#0062cc", height=36)
        self.create_btn.pack(side="left")
        return f

    # ==================== SOLVE ====================
    def _build_solve_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="还原拼图", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="both", expand=True)

        r2 = ctk.CTkFrame(card, fg_color="transparent")
        r2.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkButton(r2, text="选择拼图", font=ctk.CTkFont(size=13),
                      command=self._choose_puzzle).pack(side="left", padx=(0, 8))
        self.puzzle_label = ctk.CTkLabel(r2, text="尚未选择", font=ctk.CTkFont(size=12),
                                          text_color="#6e6e73")
        self.puzzle_label.pack(side="left")

        r2b = ctk.CTkFrame(card, fg_color="transparent")
        r2b.pack(fill="x", padx=16, pady=(0, 10))
        self.solve_btn = ctk.CTkButton(r2b, text="▶  开始还原", command=self._solve_puzzle,
                                        fg_color="#007aff", hover_color="#0062cc", height=36)
        self.solve_btn.pack(side="left", padx=(0, 8))
        self.cancel_btn = ctk.CTkButton(r2b, text="取消", command=self._cancel,
                                         fg_color="#c42b1c", hover_color="#a12218",
                                         height=36, state="disabled")
        self.cancel_btn.pack(side="right")

        r2c = ctk.CTkFrame(card, fg_color="transparent")
        r2c.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(r2c, text="输出:", width=60).pack(side="left")
        self.out_var = ctk.StringVar(value=path_os.join(OUTPUT_DIR, "solved_result.png"))
        ctk.CTkEntry(r2c, textvariable=self.out_var).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(r2c, text="...", width=40, command=self._choose_output).pack(side="left")
        return f

    # ==================== PARAMS ====================
    def _build_params_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="参数设置", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="x")

        def param_row(parent, label, var, width=80):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=(14, 8))
            ctk.CTkLabel(r, text=label, width=120).pack(side="left")
            ctk.CTkEntry(r, textvariable=var, width=width).pack(side="left", padx=6)
            return r

        self.size_var = ctk.StringVar(value=str(DEFAULT_PIECE_SIZE))
        param_row(card, "碎片大小:", self.size_var, 80)
        ctk.CTkLabel(card, text="  (32-128 px，须整除图片宽高)", font=ctk.CTkFont(size=11),
                     text_color="#6e6e73", anchor="w").pack(fill="x", padx=150, pady=(0, 8))

        self.gen_var = ctk.StringVar(value=str(DEFAULT_GENERATIONS))
        param_row(card, "进化代数:", self.gen_var, 80)
        ctk.CTkLabel(card, text="  (遗传算法迭代次数，越大越准但越慢)", font=ctk.CTkFont(size=11),
                     text_color="#6e6e73", anchor="w").pack(fill="x", padx=150, pady=(0, 8))

        self.pop_var = ctk.StringVar(value=str(DEFAULT_POPULATION))
        param_row(card, "种群大小:", self.pop_var, 80)
        ctk.CTkLabel(card, text="  (每代候选解数量，越大越稳但越慢)", font=ctk.CTkFont(size=11),
                     text_color="#6e6e73", anchor="w").pack(fill="x", padx=150, pady=(0, 14))
        return f

    # ==================== LOG ====================
    def _build_log_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="运行日志", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="both", expand=True)

        self.log_text = ctk.CTkTextbox(card, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_text.pack(fill="both", expand=True, padx=16, pady=16)
        return f

    # ==================== ACTIONS ====================
    def _log(self, msg):
        self._msg_queue.put(("log", msg))

    def _poll_queue(self):
        try:
            while True:
                typ, data = self._msg_queue.get_nowait()
                if typ == "log":
                    self._write_log(data)
                elif typ == "done":
                    self._on_thread_done(data)
        except Empty:
            pass
        self.after(100, self._poll_queue)

    def _write_log(self, msg):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def _auto_adapt(self):
        if not self.src_path:
            messagebox.showerror("错误", "请先选择原图"); return
        self._log("分析图片尺寸...")
        w, h = _get_image_dimensions(self.src_path)
        self._log(f"图片尺寸: {w} × {h}")
        best, alternatives = _suggest_auto_config(w, h)
        if best is None:
            self._log(f"图片 {w}×{h} 无合适的碎片方案"); return
        piece_size, cols, rows, total = best
        self.size_var.set(str(piece_size))
        gen = max(10, min(200, total // 2))
        pop = max(50, min(2000, total * 2))
        self.gen_var.set(str(gen))
        self.pop_var.set(str(pop))
        self._log(f"碎片 {piece_size}px  网格 {cols}×{rows}  共 {total} 片")
        self._log(f"建议: 代数={gen}  种群={pop}")

    def _choose_src(self):
        p = filedialog.askopenfilename(title="选择原图",
            filetypes=[("图片","*.jpg *.jpeg *.png *.bmp *.gif")])
        if p:
            self.src_path = p
            self.src_label.configure(text=p, text_color="#ffffff")
            self._log(f"已选原图: {p}")

    def _choose_puzzle(self):
        p = filedialog.askopenfilename(title="选择拼图",
            filetypes=[("图片","*.jpg *.jpeg *.png *.bmp *.gif")])
        if p:
            self.puzzle_path = p
            self.puzzle_label.configure(text=p, text_color="#ffffff")
            self._log(f"已选拼图: {p}")

    def _choose_output(self):
        p = filedialog.asksaveasfilename(title="保存还原结果", defaultextension=".png",
            filetypes=[("PNG","*.png"),("JPEG","*.jpg")])
        if p: self.out_var.set(p)

    def _create_puzzle(self):
        if not self.src_path:
            messagebox.showerror("错误", "请先选择原图"); return
        piece_size = int(self.size_var.get())
        if not _is_piece_size_valid(self.src_path, piece_size):
            self._log(f"图片尺寸不能整除 {piece_size}px，智能裁剪中...")
            src = _resize_for_puzzle(self.src_path, piece_size)
        else:
            src = self.src_path
        puzzle_out = path_os.join(OUTPUT_DIR,
            path_os.splitext(path_os.basename(src))[0] + "_puzzle.jpg")
        self._log("正在生成打乱拼图...")
        self._run_cmd([sys.executable, "-m", "gaps.cli",
            "create", src, puzzle_out, "--size", str(piece_size)],
            on_ok=lambda: self._on_puzzle_created(puzzle_out))

    def _on_puzzle_created(self, puzzle_out):
        self.puzzle_path = puzzle_out
        self.puzzle_label.configure(text=puzzle_out, text_color="#ffffff")
        self._log(f"拼图已生成: {puzzle_out}")

    def _solve_puzzle(self):
        if not self.puzzle_path:
            messagebox.showerror("错误", "请先选择拼图"); return
        output = self.out_var.get().strip() or path_os.join(OUTPUT_DIR, "solved_result.png")
        piece_size = int(self.size_var.get())
        generations = int(self.gen_var.get())
        population = int(self.pop_var.get())
        self._log(f"输出: {output}")
        self._log("正在还原拼图...")
        self._run_cmd([sys.executable, "-m", "gaps.cli",
            "run", self.puzzle_path, output,
            "--size", str(piece_size),
            "--generations", str(generations),
            "--population", str(population)],
            on_ok=lambda: self._log(f"还原完成: {output}"))

    def _run_cmd(self, cmd, on_ok=None):
        if self._running: return
        self._running = True
        self._cancel_flag = False
        self.create_btn.configure(state="disabled")
        self.solve_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.status_label.configure(text="运行中...", text_color="#007aff")

        def target():
            cmd_str = " ".join(str(c) for c in cmd)
            self._msg_queue.put(("log", f"执行: {cmd_str}"))
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, cwd=GAPS_ROOT,
                    encoding="utf-8", errors="replace")
                self._process = proc
                for line in proc.stdout:
                    if self._cancel_flag:
                        proc.terminate()
                        self._msg_queue.put(("log", "已终止"))
                        break
                    self._msg_queue.put(("log", line.rstrip()))
                proc.wait()
                rc = proc.returncode
                self._msg_queue.put(("log", f"返回码: {rc}"))
                if rc == 0 and not self._cancel_flag:
                    self._msg_queue.put(("done", "success"))
                    if on_ok: self.after(0, on_ok)
                else:
                    self._msg_queue.put(("done", "failed"))
            except Exception as e:
                self._msg_queue.put(("log", f"异常: {e}"))
                self._msg_queue.put(("done", "failed"))
            finally:
                self._process = None

        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()

    def _on_thread_done(self, status):
        self._running = False
        self.create_btn.configure(state="normal")
        self.solve_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_label.configure(
            text="✅ 完成" if status == "success" else "❌ 失败",
            text_color="#34c759" if status == "success" else "#c42b1c")

    def _cancel(self):
        self._cancel_flag = True
        self._msg_queue.put(("log", "正在取消..."))
        self.status_label.configure(text="取消中...", text_color="#e87800")
        self.cancel_btn.configure(state="disabled")


if __name__ == "__main__":
    app = GapsGUICTk()
    app.mainloop()

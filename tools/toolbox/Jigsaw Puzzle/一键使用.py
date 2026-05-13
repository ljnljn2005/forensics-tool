import os, sys, threading, subprocess
import matplotlib
matplotlib.use("Agg")
import customtkinter as ctk
from tkinter import filedialog, messagebox
from queue import Queue, Empty
from typing import Optional
from PIL import Image

path_os = os.path
BASE_DIR = path_os.dirname(path_os.abspath(__file__))
DEFAULT_FOLDER = path_os.join(BASE_DIR, "114514")
OUTPUT_DIR = path_os.join(BASE_DIR, "10086")
GAPS_ROOT = path_os.join(BASE_DIR, "gaps-main")

IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp", ".ico", ".tif")

DEFAULT_PIECE_SIZE = 64
DEFAULT_GENERATIONS = 20
DEFAULT_POPULATION = 200
MIN_PIECE_SIZE = 32
MAX_PIECE_SIZE = 128

# ==================== GAPS helpers ====================
def _is_piece_size_valid(image_path, piece_size):
    img = Image.open(image_path)
    w, h = img.size
    return w % piece_size == 0 and h % piece_size == 0

def _get_image_dimensions(image_path):
    img = Image.open(image_path)
    return img.size

def _find_common_divisors(w, h, lo=MIN_PIECE_SIZE, hi=MAX_PIECE_SIZE):
    result = []
    for d in range(lo, min(w, h, hi) + 1):
        if w % d == 0 and h % d == 0: result.append(d)
    return result

def _suggest_auto_config(w, h):
    divisors = _find_common_divisors(w, h)
    best, best_score = None, float("inf")
    for d in divisors:
        cols, rows = w // d, h // d
        total = cols * rows
        score = abs(total - 200)
        if score < best_score: best_score, best = score, (d, cols, rows, total)
    return best

def _resize_for_puzzle(src_path, piece_size):
    img = Image.open(src_path)
    w, h = img.size
    nw, nh = (w // piece_size) * piece_size, (h // piece_size) * piece_size
    if (nw, nh) == (w, h): return src_path
    resized = img.resize((nw, nh), Image.LANCZOS)
    base, ext = os.path.splitext(src_path)
    out = base + "_adapted" + ext
    resized.save(out)
    return out

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")
SB = "#1c1c1e"
SB_HOVER = "#2c2c2e"
ACCENT = "#007aff"
GREEN = "#34c759"
RED = "#c42b1c"
ORANGE = "#e87800"


class AllInOne(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("一键使用")
        self.geometry("960x720")
        self.minsize(800, 550)

        self._m_running = False
        self._abort = False
        self._g_running = False

        # ---------- 拼图状态 ----------
        self.folder_path = DEFAULT_FOLDER if path_os.isdir(DEFAULT_FOLDER) else ""
        self.stretch_input = None
        self.src_path: Optional[str] = None
        self.puzzle_path: Optional[str] = None
        self._cancel_flag = False
        self._process: Optional[subprocess.Popen] = None
        self._msg_queue = Queue()

        # ===== TOP TAB BAR =====
        self.tab_bar = ctk.CTkFrame(self, height=44, fg_color=SB, corner_radius=0)
        self.tab_bar.pack(fill="x")
        self.tab_bar.pack_propagate(False)

        self.tab_btns = {}
        tabs = [("montage", "超级拼接"), ("stretch", "正方形转换"), ("gaps", "拼图排序")]
        for key, text in tabs:
            btn = ctk.CTkButton(self.tab_bar, text=text, fg_color="transparent",
                                hover_color=SB_HOVER, corner_radius=6, font=ctk.CTkFont(size=13),
                                command=lambda k=key: self._switch_tab(k))
            btn.pack(side="left", padx=2, pady=4, ipadx=8)
            self.tab_btns[key] = btn

        ctk.CTkLabel(self.tab_bar, text="一键使用", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#8e8e93").pack(side="right", padx=16)

        # ===== BODY: sidebar + content =====
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        self.sidebar = ctk.CTkFrame(body, width=210, fg_color=SB, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.sidebar_title = ctk.CTkLabel(self.sidebar, text="", font=ctk.CTkFont(size=14, weight="bold"),
                                           text_color="#ffffff")
        self.sidebar_title.pack(pady=(18, 2), padx=14, anchor="w")

        self.sidebar_nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_nav_frame.pack(fill="y", expand=True, pady=(12, 0))

        self.status_label = ctk.CTkLabel(self.sidebar, text="就绪", font=ctk.CTkFont(size=10),
                                          text_color="#8e8e93")
        self.status_label.pack(side="bottom", pady=10)

        self.content = ctk.CTkFrame(body, fg_color="transparent")
        self.content.pack(side="left", fill="both", expand=True)

        # build all pages
        self.all_pages = {}
        self._build_montage_pages()
        self._build_stretch_pages()
        self._build_gaps_pages()

        self._nav_btns = {}
        self._tab_pages = {}
        for k in self.all_pages:
            self.all_pages[k].pack_forget()

        self._switch_tab("montage")
        self._poll_queue()
        self.after(100, self._m_refresh)

    # ==================== TAB SWITCH ====================
    def _switch_tab(self, tab_key):
        for k, btn in self.tab_btns.items():
            if k == tab_key:
                btn.configure(fg_color=ACCENT, hover_color=ACCENT, text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", hover_color=SB_HOVER, text_color="#d1d1d6")

        titles = {"montage": "超级拼接", "stretch": "正方形转换", "gaps": "拼图排序"}
        self.sidebar_title.configure(text=titles[tab_key])

        for w in self.sidebar_nav_frame.winfo_children():
            w.destroy()
        self._nav_btns.clear()

        navs_map = {
            "montage": [("source","源文件夹"),("layout","排版设置"),("output","输出 & 预览"),("execute","执行拼接")],
            "stretch": [("s_file","输入图片"),("s_grid","网格划分"),("s_mode","拉伸模式"),("s_convert","预览 & 转换")],
            "gaps":   [("g_create","生成拼图"),("g_solve","还原拼图"),("g_params","参数设置"),("g_log","运行日志")],
        }

        for pg in self.all_pages.values():
            pg.pack_forget()

        for key, text in navs_map[tab_key]:
            btn = ctk.CTkButton(self.sidebar_nav_frame, text=text, fg_color="transparent",
                                anchor="w", font=ctk.CTkFont(size=12),
                                hover_color=SB_HOVER, corner_radius=6,
                                command=lambda k=key: self._show_page(k))
            btn.pack(fill="x", padx=10, pady=1)
            self._nav_btns[key] = btn

        if navs_map[tab_key]:
            self._show_page(navs_map[tab_key][0][0])

    def _highlight_nav(self, active_key):
        for k, btn in self._nav_btns.items():
            if k == active_key:
                btn.configure(fg_color=ACCENT, hover_color=ACCENT, text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", hover_color=SB_HOVER, text_color="#d1d1d6")

    def _show_page(self, key):
        self._highlight_nav(key)
        for p in self.all_pages.values():
            p.pack_forget()
        self.all_pages[key].pack(fill="both", expand=True, padx=14, pady=14)

    # ==================== MONTAGE PAGES ====================
    def _build_montage_pages(self):
        # source
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="源文件夹", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="both", expand=True)
        r = ctk.CTkFrame(card, fg_color="transparent"); r.pack(fill="x", padx=14, pady=(14, 6))
        self.m_folder_var = ctk.StringVar(value=self.folder_path)
        ctk.CTkEntry(r, textvariable=self.m_folder_var).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r, text="浏览", width=70, command=self._m_choose_folder).pack(side="left", padx=4)
        ctk.CTkButton(r, text="刷新", width=70, command=self._m_refresh).pack(side="left", padx=2)
        self.m_count_var = ctk.StringVar(value="共 0 张")
        ctk.CTkLabel(card, textvariable=self.m_count_var, font=ctk.CTkFont(size=11),
                     text_color="#6e6e73").pack(anchor="w", padx=16, pady=(0, 4))
        self.m_list = ctk.CTkTextbox(card, height=10, font=ctk.CTkFont(family="Consolas", size=11))
        self.m_list.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.all_pages["source"] = f

        # layout
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="排版设置", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="x")
        def row(parent, label, var, w, hint=""):
            r = ctk.CTkFrame(parent, fg_color="transparent"); r.pack(fill="x", padx=14, pady=(10, 6))
            ctk.CTkLabel(r, text=label, width=80).pack(side="left")
            ctk.CTkEntry(r, textvariable=var, width=w).pack(side="left", padx=6)
            if hint: ctk.CTkLabel(r, text=hint, font=ctk.CTkFont(size=11), text_color="#6e6e73").pack(side="left")
        self.m_cols = ctk.StringVar(value="0"); row(card, "列数:", self.m_cols, 80, "(0=自动)")
        self.m_cw = ctk.StringVar(value="200"); row(card, "单格宽:", self.m_cw, 80, "px")
        self.m_ch = ctk.StringVar(value="200"); row(card, "单格高:", self.m_ch, 80, "px")
        self.m_gap = ctk.StringVar(value="0"); row(card, "间距:", self.m_gap, 60, "px")
        r2 = ctk.CTkFrame(card, fg_color="transparent"); r2.pack(fill="x", padx=14, pady=(6, 14))
        ctk.CTkLabel(r2, text="背景色:", width=80).pack(side="left")
        self.m_bg = ctk.StringVar(value="white")
        ctk.CTkComboBox(r2, variable=self.m_bg, width=100,
                        values=["white","black","gray","#f0f0f0","#333333","#ffcc00"]).pack(side="left", padx=6)
        ctk.CTkLabel(r2, text="排序:", width=70).pack(side="left")
        self.m_sort = ctk.StringVar(value="名称升序")
        ctk.CTkComboBox(r2, variable=self.m_sort, width=150,
                        values=["名称升序","名称降序","修改时间升序","修改时间降序"]).pack(side="left", padx=6)
        self.all_pages["layout"] = f

        # output
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="输出 & 预览", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="both", expand=True)
        r = ctk.CTkFrame(card, fg_color="transparent"); r.pack(fill="x", padx=14, pady=(14, 6))
        self.m_out = ctk.StringVar(value=path_os.join(self.folder_path or ".", "拼接结果.jpg"))
        ctk.CTkEntry(r, textvariable=self.m_out).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r, text="浏览", width=70, command=self._m_choose_out).pack(side="left", padx=4)
        self.m_info = ctk.CTkTextbox(card, height=10, font=ctk.CTkFont(family="Consolas", size=11))
        self.m_info.pack(fill="both", expand=True, padx=14, pady=(6, 14))
        self.all_pages["output"] = f

        # execute
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="执行拼接", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="both", expand=True)
        self.m_progress = ctk.CTkProgressBar(card); self.m_progress.pack(fill="x", padx=14, pady=(18, 4)); self.m_progress.set(0)
        self.m_prog_label = ctk.CTkLabel(card, text="等待执行", font=ctk.CTkFont(size=11), text_color="#6e6e73")
        self.m_prog_label.pack(anchor="w", padx=16, pady=(0, 14))
        br = ctk.CTkFrame(card, fg_color="transparent"); br.pack(fill="x", padx=14, pady=(0, 14))
        self.m_go = ctk.CTkButton(br, text="▶  开始拼接", command=self._m_start, fg_color=ACCENT, hover_color="#0062cc", height=36)
        self.m_go.pack(side="left", padx=(0, 8))
        self.m_abort = ctk.CTkButton(br, text="取消", command=self._m_abort, fg_color=RED, hover_color="#a12218", height=36, state="disabled")
        self.m_abort.pack(side="left")
        ctk.CTkButton(br, text="打开输出文件夹", command=self._m_open_dir, fg_color="transparent",
                      border_width=1, border_color="#c6c6c8", text_color="#d1d1d6", height=36).pack(side="right")
        self.all_pages["execute"] = f

    def _m_get_files(self, fld):
        fs = []
        for n in os.listdir(fld):
            if n.lower().endswith(IMG_EXTS): fs.append(path_os.join(fld, n))
        m = self.m_sort.get()
        if m=="名称升序": return sorted(fs)
        if m=="名称降序": return sorted(fs, reverse=True)
        if m=="修改时间升序": return sorted(fs, key=lambda f:path_os.getmtime(f))
        if m=="修改时间降序": return sorted(fs, key=lambda f:path_os.getmtime(f), reverse=True)
        return sorted(fs)

    def _m_update_info(self):
        self.m_info.delete("1.0","end")
        if not self.folder_path or not path_os.isdir(self.folder_path):
            self.m_info.insert("end","请先选择源文件夹。\n"); return
        fs = self._m_get_files(self.folder_path); total = len(fs)
        if total==0: self.m_info.insert("end","文件夹中没有图片。\n"); return
        try: cols = int(self.m_cols.get()) or max(int(total**0.5),1)
        except: cols = max(int(total**0.5),1)
        try: cw=int(self.m_cw.get()); ch=int(self.m_ch.get()); gap=int(self.m_gap.get())
        except: return
        rows = (total+cols-1)//cols; can_w=cols*cw+(cols+1)*gap; can_h=rows*ch+(rows+1)*gap
        for l in [f"总数:{total}  网格:{cols}×{rows}   {cw}×{ch}px  画布:{can_w}×{can_h}px  ~{(can_w*can_h*4)/1048576:.1f}MB"]:
            self.m_info.insert("end",l+"\n")
        if can_w>30000 or can_h>30000: self.m_info.insert("end","⚠ 输出尺寸极大\n")

    def _m_choose_folder(self):
        d = filedialog.askdirectory(title="选择图片文件夹")
        if d: self.folder_path = d; self.m_folder_var.set(d); self._m_refresh()

    def _m_refresh(self):
        d = self.m_folder_var.get().strip(); self.m_list.delete("1.0","end")
        if not d: self.m_count_var.set("共 0 张"); return
        self.folder_path = d; fs = self._m_get_files(d)
        n = min(len(fs), 200)
        for f in fs[:n]: self.m_list.insert("end", path_os.basename(f)+"\n")
        if len(fs)>200: self.m_list.insert("end", f"  ... 还有 {len(fs)-200} 张\n")
        self.m_count_var.set(f"共 {len(fs)} 张"); self._m_update_info()

    def _m_choose_out(self):
        p = filedialog.asksaveasfilename(defaultextension=".jpg",
            filetypes=[("JPEG","*.jpg"),("PNG","*.png"),("BMP","*.bmp")])
        if p: self.m_out.set(p)

    def _m_open_dir(self):
        o = self.m_out.get().strip()
        if o: d=path_os.dirname(o) or "."; path_os.isdir(d) and os.startfile(d)

    def _m_log(self, msg):
        self.m_info.insert("end", msg+"\n"); self.m_info.see("end"); self.update_idletasks()

    def _m_start(self):
        if self._m_running: return
        if not self.folder_path or not path_os.isdir(self.folder_path):
            messagebox.showerror("错误","请先选择源文件夹"); return
        fs = self._m_get_files(self.folder_path)
        if not fs: messagebox.showerror("错误","文件夹中没有图片"); return
        try: cols=int(self.m_cols.get())or max(int(len(fs)**0.5),1); cw=int(self.m_cw.get()); ch=int(self.m_ch.get()); gap=int(self.m_gap.get())
        except: messagebox.showerror("错误","参数格式错误"); return
        bg=self.m_bg.get()or"white"; out=self.m_out.get().strip()or path_os.join(self.folder_path,"拼接结果.jpg")
        self._m_running=True; self._abort=False
        self.m_go.configure(state="disabled"); self.m_abort.configure(state="normal")
        self.status_label.configure(text="拼接中...", text_color=ACCENT)
        threading.Thread(target=self._m_thread, args=(fs,cols,cw,ch,gap,bg,out), daemon=True).start()

    def _m_thread(self, files, cols, cw, ch, gap, bg, output):
        total=len(files); rows=(total+cols-1)//cols; can_w=cols*cw+(cols+1)*gap; can_h=rows*ch+(rows+1)*gap
        self._msg_queue.put(("m_log", f"拼接:{total}张→{cols}×{rows},{can_w}×{can_h}"))
        canvas=Image.new("RGB",(can_w,can_h),bg)
        for idx,fp in enumerate(files):
            if self._abort:
                self._msg_queue.put(("m_done", ("已取消", False, None)))
                return
            x=gap+(idx%cols)*(cw+gap);y=gap+(idx//cols)*(ch+gap)
            try:
                img=Image.open(fp)
                if img.mode in("RGBA","P","LA"):
                    img=img.convert("RGBA");t=Image.new("RGBA",img.size,bg)
                    img=Image.alpha_composite(t,img).convert("RGB")
                elif img.mode!="RGB":img=img.convert("RGB")
                img=img.resize((cw,ch),Image.LANCZOS);canvas.paste(img,(x,y));img.close()
            except Exception as e:
                self._msg_queue.put(("m_log", f"跳过{path_os.basename(fp)}:{e}"))
            if idx%50==0 or idx==total-1:
                pct=(idx+1)/total
                self._msg_queue.put(("m_progress", (pct, idx+1, total)))
        if self._abort:
            self._msg_queue.put(("m_done", ("已取消", False, None)))
            return
        self._msg_queue.put(("m_log", "保存中..."))
        try:
            canvas.save(output)
            self._msg_queue.put(("m_done", (f"完成→{output}", True, output)))
        except Exception as e:
            self._msg_queue.put(("m_log", f"保存失败: {e}"))
            self._msg_queue.put(("m_done", (f"保存失败: {e}", False, None)))

    def _m_done(self, msg, show_msg=False, out_path=None):
        self._m_running=False;self.m_go.configure(state="normal");self.m_abort.configure(state="disabled")
        self.status_label.configure(text=msg,text_color="#8e8e93")
        self.m_progress.set(0);self.m_prog_label.configure(text="")
        if show_msg and out_path:messagebox.showinfo("完成",f"拼接完成!\n\n{out_path}")

    def _m_abort(self):
        self._abort=True;self.status_label.configure(text="取消中...",text_color=ORANGE);self.m_abort.configure(state="disabled")

    # ==================== STRETCH PAGES ====================
    def _build_stretch_pages(self):
        # s_file
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="输入图片", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="both", expand=True)
        r = ctk.CTkFrame(card, fg_color="transparent"); r.pack(fill="x", padx=14, pady=(14, 8))
        self.s_path_var = ctk.StringVar()
        ctk.CTkEntry(r, textvariable=self.s_path_var, state="readonly").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r, text="选择图片", width=90, command=self._s_choose).pack(side="left", padx=4)
        self.s_thumb = ctk.CTkLabel(card, text="尚未选择图片", font=ctk.CTkFont(size=12), text_color="#6e6e73")
        self.s_thumb.pack(expand=True, pady=(0, 14))
        self.all_pages["s_file"] = f

        # s_grid
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="网格划分", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="x")
        r = ctk.CTkFrame(card, fg_color="transparent"); r.pack(fill="x", padx=14, pady=18)
        ctk.CTkLabel(r, text="列数:", width=60).pack(side="left")
        self.s_cols = ctk.StringVar(value="4")
        self.s_cols.trace_add("write", lambda *a: self._s_preview())
        ctk.CTkEntry(r, textvariable=self.s_cols, width=70).pack(side="left", padx=6)
        ctk.CTkLabel(r, text="行数:", width=60).pack(side="left", padx=(20, 0))
        self.s_rows = ctk.StringVar(value="3")
        self.s_rows.trace_add("write", lambda *a: self._s_preview())
        ctk.CTkEntry(r, textvariable=self.s_rows, width=70).pack(side="left", padx=6)
        self.all_pages["s_grid"] = f

        # s_mode
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="拉伸模式", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="x")
        self.s_mode = ctk.StringVar(value="area")
        inner = ctk.CTkFrame(card, fg_color="transparent"); inner.pack(fill="x", padx=14, pady=14)
        for txt, val in [("面积不变 (推荐)","area"),("保持宽度","keep_width"),("保持高度","keep_height")]:
            ctk.CTkRadioButton(inner, text=txt, variable=self.s_mode, value=val,
                               command=self._s_preview).pack(anchor="w", pady=3)
        self.all_pages["s_mode"] = f

        # s_convert
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="预览 & 转换", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="both", expand=True)
        self.s_preview = ctk.CTkTextbox(card, height=8, font=ctk.CTkFont(family="Consolas", size=12))
        self.s_preview.pack(fill="both", expand=True, padx=14, pady=(14, 8))
        or1 = ctk.CTkFrame(card, fg_color="transparent"); or1.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(or1, text="输出:", width=60).pack(side="left")
        self.s_out = ctk.StringVar()
        ctk.CTkEntry(or1, textvariable=self.s_out).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(or1, text="浏览", width=70, command=self._s_choose_out).pack(side="left")
        ctk.CTkButton(card, text="▶  开始转换", command=self._s_convert, fg_color=ACCENT,
                      hover_color="#0062cc", height=38).pack(pady=(6, 14))
        self.all_pages["s_convert"] = f

    def _s_choose(self):
        p = filedialog.askopenfilename(title="选择图片",
            filetypes=[("图片","*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp"),("所有","*.*")])
        if p: self.stretch_input = p; self.s_path_var.set(p); self.s_thumb.configure(text=f"{p}", text_color="#ffffff"); self._s_preview()

    def _s_choose_out(self):
        p = filedialog.asksaveasfilename(defaultextension=".png",
            filetypes=[("PNG","*.png"),("JPEG","*.jpg"),("BMP","*.bmp")])
        if p: self.s_out.set(p)

    def _s_get_cols_rows(self):
        try:
            c=int(self.s_cols.get()); r=int(self.s_rows.get())
            return (c,r) if c>0 and r>0 else (None,None)
        except: return (None,None)

    def _s_preview(self):
        self.s_preview.delete("1.0","end")
        cr=self._s_get_cols_rows()
        if not self.stretch_input:
            self.s_preview.insert("end","请先选择一张图片。\n"); return
        if cr==(None,None): self.s_preview.insert("end","请输入有效行列数。\n"); return
        cols,rows=cr
        try:
            img=Image.open(self.stretch_input);ow,oh=img.size;cw=ow/cols;ch=oh/rows
            mode=self.s_mode.get()
            if mode=="keep_width":nw,nh=ow,round(ow*rows/cols)
            elif mode=="keep_height":nw,nh=round(oh*cols/rows),oh
            else:side=(cw*ch)**0.5;nw=round(side*cols);nh=round(nw*rows/cols)
            ncw,nch=nw/cols,nh/rows
            for l in [f"原图:{ow}×{oh}  网格:{cols}×{rows}",f"格子原:{cw:.2f}×{ch:.2f}",
                      f"→拉伸后:{nw}×{nh}  格子新:{ncw:.2f}×{nch:.2f}  ✓"]:
                self.s_preview.insert("end",l+"\n")
        except Exception: self.s_preview.insert("end","预览计算异常\n")

    def _s_convert(self):
        if not self.stretch_input: messagebox.showerror("错误","请先选择图片"); return
        cr=self._s_get_cols_rows()
        if cr==(None,None): messagebox.showerror("错误","请输入有效行列数"); return
        cols,rows=cr; mode=self.s_mode.get()
        try:
            img=Image.open(self.stretch_input);ow,oh=img.size
            if mode=="keep_width":nw,nh=ow,round(ow*rows/cols)
            elif mode=="keep_height":nw,nh=round(oh*cols/rows),oh
            else:side=((ow/cols)*(oh/rows))**0.5;nw=round(side*cols);nh=round(nw*rows/cols)
            resized=img.resize((nw,nh),Image.LANCZOS)
            out=self.s_out.get().strip()
            if not out:base,ext=os.path.splitext(self.stretch_input);out=f"{base}_square{ext}"
            resized.save(out)
            self.status_label.configure(text=f"完成→{os.path.basename(out)}",text_color=GREEN)
            messagebox.showinfo("成功",f"已保存到:\n{out}")
        except Exception as e: messagebox.showerror("错误",f"转换失败:\n{e}")

    # ==================== GAPS PAGES ====================
    def _build_gaps_pages(self):
        # g_create
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="生成打乱拼图", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="both", expand=True)
        r = ctk.CTkFrame(card, fg_color="transparent"); r.pack(fill="x", padx=14, pady=(14, 8))
        ctk.CTkButton(r, text="选择原图", command=self._g_choose_src).pack(side="left", padx=(0, 8))
        self.g_src_label = ctk.CTkLabel(r, text="尚未选择", text_color="#6e6e73")
        self.g_src_label.pack(side="left")
        rb = ctk.CTkFrame(card, fg_color="transparent"); rb.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkButton(rb, text="智能适配", command=self._g_auto, fg_color=GREEN, hover_color="#2da94d", height=36).pack(side="left", padx=(0, 8))
        self.g_create_btn = ctk.CTkButton(rb, text="生成拼图", command=self._g_create, fg_color=ACCENT, hover_color="#0062cc", height=36)
        self.g_create_btn.pack(side="left")
        self.all_pages["g_create"] = f

        # g_solve
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="还原拼图", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="both", expand=True)
        r = ctk.CTkFrame(card, fg_color="transparent"); r.pack(fill="x", padx=14, pady=(14, 8))
        ctk.CTkButton(r, text="选择拼图", command=self._g_choose_puzzle).pack(side="left", padx=(0, 8))
        self.g_pzl_label = ctk.CTkLabel(r, text="尚未选择", text_color="#6e6e73")
        self.g_pzl_label.pack(side="left")
        rb = ctk.CTkFrame(card, fg_color="transparent"); rb.pack(fill="x", padx=14, pady=(0, 10))
        self.g_solve_btn = ctk.CTkButton(rb, text="▶  开始还原", command=self._g_solve, fg_color=ACCENT, hover_color="#0062cc", height=36)
        self.g_solve_btn.pack(side="left", padx=(0, 8))
        self.g_cancel_btn = ctk.CTkButton(rb, text="取消", command=self._g_cancel, fg_color=RED, hover_color="#a12218", height=36, state="disabled")
        self.g_cancel_btn.pack(side="right")
        r2 = ctk.CTkFrame(card, fg_color="transparent"); r2.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkLabel(r2, text="输出:", width=60).pack(side="left")
        self.g_out = ctk.StringVar(value=path_os.join(OUTPUT_DIR,"solved_result.png"))
        ctk.CTkEntry(r2, textvariable=self.g_out).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(r2, text="...", width=40, command=self._g_choose_out).pack(side="left")
        self.all_pages["g_solve"] = f

        # g_params
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="参数设置", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="x")
        def pr(parent, label, var, w=80):
            r=ctk.CTkFrame(parent,fg_color="transparent");r.pack(fill="x",padx=14,pady=(14,8))
            ctk.CTkLabel(r,text=label,width=120).pack(side="left")
            ctk.CTkEntry(r,textvariable=var,width=w).pack(side="left",padx=6);return r
        self.g_size = ctk.StringVar(value=str(DEFAULT_PIECE_SIZE)); pr(card,"小正方形边长:",self.g_size)
        self.g_gen = ctk.StringVar(value=str(DEFAULT_GENERATIONS)); pr(card,"进化代数:",self.g_gen)
        self.g_pop = ctk.StringVar(value=str(DEFAULT_POPULATION)); pr(card,"种群大小:",self.g_pop)
        self.all_pages["g_params"] = f

        # g_log
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="运行日志", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))
        card = ctk.CTkFrame(f); card.pack(fill="both", expand=True)
        self.g_log = ctk.CTkTextbox(card, font=ctk.CTkFont(family="Consolas", size=11))
        self.g_log.pack(fill="both", expand=True, padx=14, pady=14)
        self.all_pages["g_log"] = f

    def _g_log_msg(self, msg):
        self._msg_queue.put(("log", msg))

    def _poll_queue(self):
        try:
            while True:
                typ, data = self._msg_queue.get_nowait()
                if typ == "log":
                    self.g_log.insert("end", data+"\n"); self.g_log.see("end")
                elif typ == "m_log":
                    self._m_log(data)
                elif typ == "m_progress":
                    pct, current, total = data
                    self.m_progress.set(pct)
                    self.m_prog_label.configure(text=f"{current}/{total} ({int(pct*100)}%)")
                elif typ == "m_done":
                    msg, show_msg, out_path = data
                    self._m_done(msg, show_msg=show_msg, out_path=out_path)
                elif typ == "done":
                    status, callback = data
                    self._g_on_done(status)
                    if callback:
                        callback()
        except Empty: pass
        self.after(100, self._poll_queue)

    def _g_auto(self):
        if not self.src_path: messagebox.showerror("错误","请先选择原图"); return
        w,h=_get_image_dimensions(self.src_path);best=_suggest_auto_config(w,h)
        if not best:self._g_log_msg(f"{w}×{h}无合适方案");return
        ps,cols,rows,total=best;self.g_size.set(str(ps))
        gen=max(10,min(200,total//2));pop=max(50,min(2000,total*2))
        self.g_gen.set(str(gen));self.g_pop.set(str(pop))
        self._g_log_msg(f"碎片{ps}px 网格{cols}×{rows} 共{total}片 代数{gen} 种群{pop}")

    def _g_choose_src(self):
        p=filedialog.askopenfilename(title="选择原图",filetypes=[("图片","*.jpg *.jpeg *.png *.bmp *.gif")])
        if p:self.src_path=p;self.g_src_label.configure(text=p,text_color="#ffffff");self._g_log_msg(f"原图:{p}")

    def _g_choose_puzzle(self):
        p=filedialog.askopenfilename(title="选择拼图",filetypes=[("图片","*.jpg *.jpeg *.png *.bmp *.gif")])
        if p:self.puzzle_path=p;self.g_pzl_label.configure(text=p,text_color="#ffffff");self._g_log_msg(f"拼图:{p}")

    def _g_choose_out(self):
        p=filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png"),("JPEG","*.jpg")])
        if p:self.g_out.set(p)

    def _g_create(self):
        if not self.src_path:messagebox.showerror("错误","请先选原图");return
        ps=int(self.g_size.get())
        src=self.src_path if _is_piece_size_valid(self.src_path,ps) else _resize_for_puzzle(self.src_path,ps)
        os.makedirs(OUTPUT_DIR,exist_ok=True)
        out=path_os.join(OUTPUT_DIR,path_os.splitext(path_os.basename(src))[0]+"_puzzle.jpg")
        self._g_log_msg("生成拼图...")
        self._g_run_cmd(["create",src,out,"--size",str(ps)],on_ok=lambda:(setattr(self,'puzzle_path',out),
            self.g_pzl_label.configure(text=out,text_color="#ffffff"),self._g_log_msg(f"拼图:{out}")))

    def _g_solve(self):
        if not self.puzzle_path:messagebox.showerror("错误","请先选拼图");return
        out=self.g_out.get().strip()or path_os.join(OUTPUT_DIR,"solved_result.png")
        ps=self.g_size.get();gen=self.g_gen.get();pop=self.g_pop.get()
        # 构建 CMD 命令
        cmd_parts = [sys.executable, "-m", "gaps.cli", "run",
                     self.puzzle_path, out,
                     "--size", ps,
                     "--generations", gen,
                     "--population", pop,
                     "--selection", "tournament",
                     "--mutation", "0.02"]
        cmd_line = " ".join('"{}"'.format(p) if " " in p else p for p in cmd_parts)
        cmd_line_full = 'cd /d "{}" && {}'.format(GAPS_ROOT, cmd_line)

        # 弹出确认对话框
        dialog = ctk.CTkToplevel(self)
        dialog.title("确认执行")
        dialog.geometry("680x320")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()

        ctk.CTkLabel(dialog, text="推荐在 CMD 中执行以下命令：",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(16, 8))

        cmd_box = ctk.CTkTextbox(dialog, height=80, font=ctk.CTkFont(family="Consolas", size=11))
        cmd_box.pack(fill="x", padx=16, pady=(0, 4))
        cmd_box.insert("1.0", cmd_line_full)
        cmd_box.configure(state="disabled")

        ctk.CTkLabel(dialog, text="或点击下方按钮直接在 GUI 中执行（可能耗时较长）",
                     text_color="#8e8e93", font=ctk.CTkFont(size=11)).pack(pady=(0, 12))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(0, 16))

        def copy_and_close():
            dialog.clipboard_clear()
            dialog.clipboard_append(cmd_line_full)
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="复制命令", command=copy_and_close,
                      fg_color="#555555", hover_color="#666666", width=100, height=34).pack(side="left", padx=6)

        def confirm_and_run():
            dialog.destroy()
            self._g_log_msg(f"还原: →{out}")
            self._g_run_cmd(["run", self.puzzle_path, out,
                             "--size", ps, "--generations", gen, "--population", pop,
                             "--selection", "tournament", "--mutation", "0.02"],
                            on_ok=lambda: self._g_log_msg(f"完成:{out}"))

        ctk.CTkButton(btn_frame, text="确认执行", command=confirm_and_run,
                      fg_color=ACCENT, hover_color="#0062cc", width=100, height=34).pack(side="left", padx=6)

        ctk.CTkButton(btn_frame, text="取消", command=dialog.destroy,
                      fg_color="transparent", border_width=1, border_color="#c6c6c8",
                      text_color="#d1d1d6", width=80, height=34).pack(side="left", padx=6)

    def _g_run_cmd(self, args, on_ok=None):
        if self._g_running:return
        self._g_running=True;self._cancel_flag=False
        self.g_create_btn.configure(state="disabled");self.g_solve_btn.configure(state="disabled")
        self.g_cancel_btn.configure(state="normal");self.status_label.configure(text="运行中...",text_color=ACCENT)
        cmd=[sys.executable,"-m","gaps.cli"]+args
        self._g_stop_event=threading.Event()

        def reader(proc, stop):
            import io
            for line in io.TextIOWrapper(proc.stdout, encoding="utf-8", errors="replace"):
                if stop.is_set():break
                self._msg_queue.put(("log",line.rstrip()))
                if stop.is_set():break

        def target():
            self._g_log_msg(f"执行:{' '.join(cmd)}")
            proc=None;rd=None
            try:
                proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                       cwd=GAPS_ROOT,text=False)
                self._process=proc
                rd=threading.Thread(target=reader,args=(proc,self._g_stop_event),daemon=True)
                rd.start()
                while rd.is_alive():
                    rd.join(timeout=0.2)
                    if self._cancel_flag and proc.poll() is None:
                        proc.terminate();self._msg_queue.put(("log","已终止"))
                        self._g_stop_event.set();break
                if not self._cancel_flag:proc.wait()
                rc=proc.returncode
                self._msg_queue.put(("log",f"返回码:{rc}"))
                if rc==0 and not self._cancel_flag:
                    self._msg_queue.put(("done",("success", on_ok)))
                else:self._msg_queue.put(("done",("failed", None)))
            except Exception as e:self._msg_queue.put(("log",f"异常:{e}"));self._msg_queue.put(("done",("failed", None)))
            finally:
                self._g_stop_event.set()
                if rd and rd.is_alive():rd.join(timeout=1)
                if proc and proc.poll() is None:
                    try:proc.kill();proc.wait(timeout=2)
                    except:pass
                self._process=None
        threading.Thread(target=target,daemon=True).start()

    def _g_drop_running(self):
        if self._g_running:
            self._g_running=False
            self.g_create_btn.configure(state="normal");self.g_solve_btn.configure(state="normal")
            self.g_cancel_btn.configure(state="disabled")

    def _g_on_done(self,status):
        self._g_drop_running()
        self.status_label.configure(text="✅完成"if status=="success"else"❌失败",
                                     text_color=GREEN if status=="success"else RED)

    def _g_cancel(self):
        self._cancel_flag=True
        if hasattr(self,"_g_stop_event"):self._g_stop_event.set()
        self._msg_queue.put(("log","取消中..."));self.g_cancel_btn.configure(state="disabled")
        self._g_drop_running()


if __name__ == "__main__":
    AllInOne().mainloop()

import os, sys, threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FOLDER = os.path.join(BASE_DIR, "114514")
IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp", ".ico", ".tif")


def get_image_files(folder):
    if not os.path.isdir(folder):
        return []
    files = []
    for name in os.listdir(folder):
        if name.lower().endswith(IMG_EXTS):
            files.append(os.path.join(folder, name))
    return sorted(files)


class SuperMontageCTk(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("超级拼接")
        self.geometry("900x680")
        self.minsize(700, 500)

        self.folder_path = DEFAULT_FOLDER if os.path.isdir(DEFAULT_FOLDER) else ""
        self._running = False
        self._abort = False

        # ---- sidebar ----
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color="#1c1c1e")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="超级拼接", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#ffffff").pack(pady=(20, 0), padx=16, anchor="w")
        ctk.CTkLabel(self.sidebar, text="PIL 循环拼接 · 数千张无压力",
                     font=ctk.CTkFont(size=11), text_color="#8e8e93").pack(pady=(4, 20), padx=16, anchor="w")

        self.nav_btns = {}
        for key, text in [("source","源文件夹"), ("layout","排版设置"), ("output","输出设置"), ("execute","执行拼接")]:
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
        self.pages["source"] = self._build_source_page()
        self.pages["layout"] = self._build_layout_page()
        self.pages["output"] = self._build_output_page()
        self.pages["execute"] = self._build_execute_page()

        self._switch_page("source")

    def _switch_page(self, key):
        for k, btn in self.nav_btns.items():
            if k == key:
                btn.configure(fg_color="#007aff", hover_color="#007aff", text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", hover_color="#2c2c2e", text_color="#d1d1d6")
        for p in self.pages.values():
            p.pack_forget()
        self.pages[key].pack(fill="both", expand=True, padx=16, pady=16)

    # ==================== SOURCE ====================
    def _build_source_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="源文件夹", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="both", expand=True)

        r1 = ctk.CTkFrame(card, fg_color="transparent")
        r1.pack(fill="x", padx=16, pady=(16, 6))
        self.folder_var = ctk.StringVar(value=self.folder_path)
        ctk.CTkEntry(r1, textvariable=self.folder_var).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r1, text="浏览", width=70, command=self._choose_folder).pack(side="left", padx=(6, 2))
        ctk.CTkButton(r1, text="刷新", width=70, command=self._refresh).pack(side="left", padx=2)

        self.file_count_var = ctk.StringVar(value="共 0 张图片")
        ctk.CTkLabel(card, textvariable=self.file_count_var, font=ctk.CTkFont(size=11),
                     text_color="#6e6e73").pack(anchor="w", padx=18, pady=(0, 4))

        self.file_listbox = ctk.CTkTextbox(card, height=10, font=ctk.CTkFont(family="Consolas", size=11))
        self.file_listbox.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        return f

    def _choose_folder(self):
        d = filedialog.askdirectory(title="选择图片文件夹")
        if d:
            self.folder_path = d; self.folder_var.set(d); self._refresh()

    def _refresh(self):
        d = self.folder_var.get().strip()
        self.file_listbox.delete("1.0","end")
        if not d: self.file_count_var.set("共 0 张图片"); return
        self.folder_path = d
        fs = self._get_sorted(d)
        show_n = min(len(fs), 200)
        for f in fs[:show_n]: self.file_listbox.insert("end", os.path.basename(f)+"\n")
        if len(fs) > 200: self.file_listbox.insert("end", f"  ... 还有 {len(fs)-200} 张\n")
        self.file_count_var.set(f"共 {len(fs)} 张图片")
        self._update_info()

    # ==================== LAYOUT ====================
    def _build_layout_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="排版设置", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="x")

        def spin_row(parent, label, var, frm, to, w, hint=""):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=(10, 6))
            ctk.CTkLabel(r, text=label, width=80).pack(side="left")
            ctk.CTkEntry(r, textvariable=var, width=w).pack(side="left", padx=6)
            if hint: ctk.CTkLabel(r, text=hint, font=ctk.CTkFont(size=11),
                                   text_color="#6e6e73").pack(side="left")

        self.cols_var = ctk.StringVar(value="0")
        spin_row(card, "列数:", self.cols_var, 0, 10000, 80, "(0=自动)")
        self.cw_var = ctk.StringVar(value="200")
        spin_row(card, "单格宽:", self.cw_var, 1, 8192, 80, "px")
        self.ch_var = ctk.StringVar(value="200")
        spin_row(card, "单格高:", self.ch_var, 1, 8192, 80, "px")
        self.gap_var = ctk.StringVar(value="0")
        spin_row(card, "间距:", self.gap_var, 0, 100, 60, "px")

        r2 = ctk.CTkFrame(card, fg_color="transparent")
        r2.pack(fill="x", padx=16, pady=(6, 14))
        ctk.CTkLabel(r2, text="背景色:", width=80).pack(side="left")
        self.bg_var = ctk.StringVar(value="white")
        ctk.CTkComboBox(r2, variable=self.bg_var, width=100,
                        values=["white","black","gray","#f0f0f0","#333333","#ffcc00"]).pack(side="left", padx=6)
        ctk.CTkLabel(r2, text="  排序:", width=70).pack(side="left")
        self.sort_var = ctk.StringVar(value="名称升序")
        ctk.CTkComboBox(r2, variable=self.sort_var, width=150,
                        values=["名称升序","名称降序","修改时间升序","修改时间降序"]).pack(side="left", padx=6)
        return f

    # ==================== OUTPUT ====================
    def _build_output_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="输出设置", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="x")

        r = ctk.CTkFrame(card, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=(16, 6))
        self.out_var = ctk.StringVar(value=os.path.join(self.folder_path or ".", "拼接结果.jpg"))
        ctk.CTkEntry(r, textvariable=self.out_var).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r, text="浏览", width=70, command=self._choose_output).pack(side="left", padx=6)

        self.info_text = ctk.CTkTextbox(card, height=12, font=ctk.CTkFont(family="Consolas", size=11))
        self.info_text.pack(fill="x", padx=16, pady=(6, 16))
        return f

    # ==================== EXECUTE ====================
    def _build_execute_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="执行拼接", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="both", expand=True)

        self.progress = ctk.CTkProgressBar(card, width=500)
        self.progress.pack(fill="x", padx=16, pady=(20, 4))
        self.progress.set(0)
        self.progress_label = ctk.CTkLabel(card, text="等待执行", font=ctk.CTkFont(size=11),
                                            text_color="#6e6e73")
        self.progress_label.pack(anchor="w", padx=20, pady=(0, 14))

        br = ctk.CTkFrame(card, fg_color="transparent")
        br.pack(fill="x", padx=16, pady=(0, 16))
        self.go_btn = ctk.CTkButton(br, text="▶  开始拼接", command=self._start,
                                     fg_color="#007aff", hover_color="#0062cc", height=36)
        self.go_btn.pack(side="left", padx=(0, 8))
        self.abort_btn = ctk.CTkButton(br, text="取消", command=self._do_abort,
                                        fg_color="#c42b1c", hover_color="#a12218", height=36,
                                        state="disabled")
        self.abort_btn.pack(side="left")
        ctk.CTkButton(br, text="打开输出文件夹", command=self._open_out_dir,
                      fg_color="transparent", border_width=1, border_color="#c6c6c8",
                      text_color=("#1a1a1a","#d1d1d6"), height=36).pack(side="right")
        return f

    # ==================== LOGIC ====================
    def _log(self, msg):
        self.info_text.insert("end", msg+"\n")
        self.info_text.see("end")
        self.update_idletasks()

    def _get_sorted(self, fld):
        fs = []
        for n in os.listdir(fld):
            if n.lower().endswith(IMG_EXTS): fs.append(os.path.join(fld, n))
        m = self.sort_var.get()
        if m=="名称升序": return sorted(fs)
        if m=="名称降序": return sorted(fs, reverse=True)
        if m=="修改时间升序": return sorted(fs, key=lambda f:os.path.getmtime(f))
        if m=="修改时间降序": return sorted(fs, key=lambda f:os.path.getmtime(f), reverse=True)
        return sorted(fs)

    def _update_info(self):
        self.info_text.delete("1.0","end")
        if not self.folder_path or not os.path.isdir(self.folder_path):
            self.info_text.insert("end","请先选择源文件夹。\n"); return
        fs = self._get_sorted(self.folder_path)
        total = len(fs)
        if total==0: self.info_text.insert("end","文件夹中没有图片。\n"); return
        try: cols = int(self.cols_var.get()) or max(int(total**0.5),1)
        except: cols = max(int(total**0.5),1)
        try: cw=int(self.cw_var.get()); ch=int(self.ch_var.get()); gap=int(self.gap_var.get())
        except: return
        rows = (total+cols-1)//cols; can_w=cols*cw+(cols+1)*gap; can_h=rows*ch+(rows+1)*gap
        mem = (can_w*can_h*4)/(1024*1024)
        for l in [f"图片总数 : {total}", f"网格布局 : {cols}列×{rows}行",
                  f"每格尺寸 : {cw}×{ch}px  间距:{gap}px",
                  f"输出画布 : {can_w}×{can_h}px  ~{mem:.1f}MB"]:
            self.info_text.insert("end",l+"\n")
        if can_w>30000 or can_h>30000: self.info_text.insert("end","⚠ 输出尺寸极大\n")

    def _choose_output(self):
        p = filedialog.asksaveasfilename(defaultextension=".jpg",
            filetypes=[("JPEG","*.jpg"),("PNG","*.png"),("BMP","*.bmp")])
        if p: self.out_var.set(p)

    def _open_out_dir(self):
        o = self.out_var.get().strip()
        if o: d=os.path.dirname(o) or "."; os.path.isdir(d) and os.startfile(d)

    def _start(self):
        if self._running: return
        if not self.folder_path or not os.path.isdir(self.folder_path):
            messagebox.showerror("错误","请先选择源文件夹"); return
        fs = self._get_sorted(self.folder_path)
        if not fs: messagebox.showerror("错误","文件夹中没有图片"); return
        try: cols = int(self.cols_var.get()) or max(int(len(fs)**0.5),1)
        except: cols = max(int(len(fs)**0.5),1)
        try: cw=int(self.cw_var.get()); ch=int(self.ch_var.get()); gap=int(self.gap_var.get())
        except: messagebox.showerror("错误","参数格式错误"); return
        bg = self.bg_var.get() or "white"
        out = self.out_var.get().strip() or os.path.join(self.folder_path,"拼接结果.jpg")

        self._running = True; self._abort = False
        self.go_btn.configure(state="disabled"); self.abort_btn.configure(state="normal")
        self.status_label.configure(text="拼接中...", text_color="#007aff")
        threading.Thread(target=self._stitch_thread,
                         args=(fs,cols,cw,ch,gap,bg,out), daemon=True).start()

    def _stitch_thread(self, files, cols, cw, ch, gap, bg, output):
        total = len(files)
        rows = (total+cols-1)//cols
        can_w, can_h = cols*cw+(cols+1)*gap, rows*ch+(rows+1)*gap
        self.after(0, lambda: self._log(f"开始拼接: {total}张 → {cols}×{rows}, {can_w}×{can_h}"))
        canvas = Image.new("RGB", (can_w,can_h), bg)
        for idx, fp in enumerate(files):
            if self._abort: self.after(0,lambda:self._done("已取消")); return
            x = gap+(idx%cols)*(cw+gap); y = gap+(idx//cols)*(ch+gap)
            try:
                img = Image.open(fp)
                if img.mode in ("RGBA","P","LA"):
                    img=img.convert("RGBA"); t=Image.new("RGBA",img.size,bg)
                    img=Image.alpha_composite(t,img).convert("RGB")
                elif img.mode!="RGB": img=img.convert("RGB")
                img = img.resize((cw,ch), Image.LANCZOS)
                canvas.paste(img,(x,y)); img.close()
            except Exception as e: self.after(0,lambda m=str(e):self._log(f"跳过 {os.path.basename(fp)}:{m}"))
            if idx%50==0 or idx==total-1:
                pct=(idx+1)/total
                self.after(0,lambda v=pct, i=idx, t=total: (self.progress.set(v),
                    self.progress_label.configure(text=f"{i+1}/{t} ({int(v*100)}%)")))
        if self._abort: self.after(0,lambda:self._done("已取消")); return
        self.after(0,lambda:self._log("保存中...")); canvas.save(output)
        self._done(f"✓ 拼接完成 → {output}", show_msg=True, out_path=output)

    def _done(self, msg, show_msg=False, out_path=None):
        def _update():
            self._running=False; self.go_btn.configure(state="normal")
            self.abort_btn.configure(state="disabled")
            self.status_label.configure(text=msg, text_color="#8e8e93")
            self.progress.set(0); self.progress_label.configure(text="")
            if show_msg and out_path: messagebox.showinfo("完成", f"拼接完成!\n\n{out_path}")
        self.after(0,_update)

    def _do_abort(self):
        self._abort = True
        self.status_label.configure(text="取消中...", text_color="#e87800")
        self.abort_btn.configure(state="disabled")

if __name__ == "__main__":
    app = SuperMontageCTk()
    app.mainloop()

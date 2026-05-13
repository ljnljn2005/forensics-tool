import os, sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class SquareConverterCTk(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("正方形转换器")
        self.geometry("880x620")
        self.minsize(680, 480)

        self.input_path = None
        self.thumb_tk = None

        # ---- sidebar ----
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color="#1c1c1e")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="正方形转换器", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#ffffff").pack(pady=(20, 0), padx=16, anchor="w")
        ctk.CTkLabel(self.sidebar, text="网格拉伸 · 格子变正方形",
                     font=ctk.CTkFont(size=11), text_color="#8e8e93").pack(pady=(4, 20), padx=16, anchor="w")

        self.nav_btns = {}
        for key, text in [("file","输入图片"), ("grid","网格划分"), ("mode","拉伸模式"), ("convert","预览 & 转换")]:
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
        self.pages["file"] = self._build_file_page()
        self.pages["grid"] = self._build_grid_page()
        self.pages["mode"] = self._build_mode_page()
        self.pages["convert"] = self._build_convert_page()

        self._switch_page("file")

    def _switch_page(self, key):
        for k, btn in self.nav_btns.items():
            if k == key:
                btn.configure(fg_color="#007aff", hover_color="#007aff", text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", hover_color="#2c2c2e", text_color="#d1d1d6")
        for p in self.pages.values():
            p.pack_forget()
        self.pages[key].pack(fill="both", expand=True, padx=16, pady=16)

    # ==================== FILE ====================
    def _build_file_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="输入图片", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="both", expand=True)

        r1 = ctk.CTkFrame(card, fg_color="transparent")
        r1.pack(fill="x", padx=16, pady=(16, 8))
        self.path_var = ctk.StringVar()
        ctk.CTkEntry(r1, textvariable=self.path_var, state="readonly").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r1, text="选择图片", width=90, command=self._choose_image).pack(side="left", padx=(6, 0))

        self.thumb_label = ctk.CTkLabel(card, text="尚未选择图片", font=ctk.CTkFont(size=13),
                                         text_color="#6e6e73")
        self.thumb_label.pack(expand=True, pady=(0, 16))
        return f

    def _choose_image(self):
        p = filedialog.askopenfilename(title="选择图片",
            filetypes=[("图片文件","*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp"), ("所有","*.*")])
        if not p: return
        self.input_path = p
        self.path_var.set(p)
        self._show_thumbnail()
        self._refresh_preview()

    def _show_thumbnail(self):
        try:
            img = Image.open(self.input_path)
            w, h = img.size
            max_s = 220
            ratio = min(max_s / w, max_s / h, 1)
            thumb = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            self.thumb_tk = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
            self.thumb_label.configure(image=self.thumb_tk, text=f"{w} × {h} 像素",
                                        compound="top", text_color="#6e6e73")
        except Exception:
            self.thumb_label.configure(image=None, text="无法加载预览", text_color="#c42b1c")

    # ==================== GRID ====================
    def _build_grid_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="网格划分", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="x")

        r = ctk.CTkFrame(card, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=20)

        ctk.CTkLabel(r, text="列数 (每行四边形数量):", width=180).pack(side="left")
        self.cols_var = ctk.StringVar(value="4")
        self.cols_var.trace_add("write", lambda *a: self._refresh_preview())
        ctk.CTkEntry(r, textvariable=self.cols_var, width=80).pack(side="left", padx=6)

        ctk.CTkLabel(r, text="行数 (每列四边形数量):", width=180).pack(side="left", padx=(20, 0))
        self.rows_var = ctk.StringVar(value="3")
        self.rows_var.trace_add("write", lambda *a: self._refresh_preview())
        ctk.CTkEntry(r, textvariable=self.rows_var, width=80).pack(side="left", padx=6)
        return f

    # ==================== MODE ====================
    def _build_mode_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="拉伸模式", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="x")

        self.mode_var = ctk.StringVar(value="area")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)
        for text, val in [
            ("面积不变 — 宽高同时调整，总面积基本不变 (推荐)", "area"),
            ("保持宽度 — 宽度不变，只拉伸高度", "keep_width"),
            ("保持高度 — 高度不变，只拉伸宽度", "keep_height"),
        ]:
            ctk.CTkRadioButton(inner, text=text, variable=self.mode_var, value=val,
                               command=self._refresh_preview).pack(anchor="w", pady=4)
        return f

    # ==================== CONVERT ====================
    def _build_convert_page(self):
        f = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(f, text="预览 & 转换", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 12))

        card = ctk.CTkFrame(f)
        card.pack(fill="both", expand=True)

        self.preview_text = ctk.CTkTextbox(card, height=10, font=ctk.CTkFont(family="Consolas", size=12))
        self.preview_text.pack(fill="both", expand=True, padx=16, pady=(16, 8))

        or1 = ctk.CTkFrame(card, fg_color="transparent")
        or1.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(or1, text="输出路径:", width=80).pack(side="left")
        self.out_var = ctk.StringVar()
        ctk.CTkEntry(or1, textvariable=self.out_var).pack(side="left", fill="x", expand=True, padx=6)
        ctk.CTkButton(or1, text="浏览", width=70, command=self._choose_output).pack(side="left")

        self.convert_btn = ctk.CTkButton(card, text="▶  开始转换", command=self._convert,
                                          fg_color="#007aff", hover_color="#0062cc", height=38)
        self.convert_btn.pack(pady=(6, 16))
        return f

    # ==================== LOGIC ====================
    def _get_cols_rows(self):
        try:
            cols = int(self.cols_var.get())
            rows = int(self.rows_var.get())
            if cols < 1 or rows < 1: return None, None
            return cols, rows
        except ValueError:
            return None, None

    def _refresh_preview(self, *_):
        self.preview_text.delete("1.0", "end")
        cols, rows = self._get_cols_rows()
        if not self.input_path:
            self.preview_text.insert("end", "请先选择一张图片。\n")
            if cols and rows: self.preview_text.insert("end", f"当前网格: {cols}列 × {rows}行\n")
            return
        if cols is None or rows is None:
            self.preview_text.insert("end", "请输入有效的行列数。\n"); return
        try:
            img = Image.open(self.input_path)
            ow, oh = img.size
            cw = ow / cols; ch = oh / rows
            mode = self.mode_var.get()
            if mode == "keep_width":
                nw, nh = ow, round(ow * rows / cols)
            elif mode == "keep_height":
                nw, nh = round(oh * cols / rows), oh
            else:
                side = (cw * ch) ** 0.5
                nw = round(side * cols)
                nh = round(nw * rows / cols)
            ncw, nch = nw / cols, nh / rows
            for l in [
                f"原图  : {ow:>6} × {oh:<6}  网格: {cols}×{rows}",
                f"格子原: {cw:>6.2f} × {ch:<6.2f}",
                "──────────────────────────",
                f"拉伸后: {nw:>6} × {nh:<6}",
                f"格子新: {ncw:>6.2f} × {nch:<6.2f}  ✓ 正方形",
            ]:
                self.preview_text.insert("end", l + "\n")
            if abs(ncw - nch) > 0.01:
                self.preview_text.insert("end", f"  (像素偏差: Δ={abs(ncw - nch):.2f} px)\n")
        except Exception:
            self.preview_text.insert("end", "预览计算异常\n")

    def _choose_output(self):
        p = filedialog.asksaveasfilename(title="保存为", defaultextension=".png",
            filetypes=[("PNG","*.png"),("JPEG","*.jpg"),("BMP","*.bmp"),("所有","*.*")])
        if p: self.out_var.set(p)

    def _convert(self):
        if not self.input_path:
            messagebox.showerror("错误", "请先选择图片"); return
        cols, rows = self._get_cols_rows()
        if cols is None or rows is None:
            messagebox.showerror("错误", "请输入有效行列数"); return
        mode = self.mode_var.get()
        try:
            img = Image.open(self.input_path)
            ow, oh = img.size
            if mode == "keep_width":
                nw, nh = ow, round(ow * rows / cols)
            elif mode == "keep_height":
                nw, nh = round(oh * cols / rows), oh
            else:
                side = ((ow / cols) * (oh / rows)) ** 0.5
                nw = round(side * cols)
                nh = round(nw * rows / cols)
            resized = img.resize((nw, nh), Image.LANCZOS)
            out_path = self.out_var.get().strip()
            if not out_path:
                base, ext = os.path.splitext(self.input_path)
                out_path = f"{base}_square{ext}"
            resized.save(out_path)
            self.status_label.configure(text=f"完成 → {os.path.basename(out_path)}", text_color="#34c759")
            messagebox.showinfo("成功", f"已保存到:\n{out_path}")
        except Exception as e:
            messagebox.showerror("错误", f"转换失败:\n{e}")
            self.status_label.configure(text="转换失败", text_color="#c42b1c")


if __name__ == "__main__":
    app = SquareConverterCTk()
    app.mainloop()

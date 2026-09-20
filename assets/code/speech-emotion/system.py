import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

import numpy as np
import torch
import torch.nn as nn
import librosa
import librosa.display

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg



class SER1DCNN(nn.Module):
    def __init__(self, num_classes=8):
        super().__init__()

        def block(in_ch, out_ch, k):
            return nn.Sequential(
                nn.Conv1d(in_ch, out_ch, kernel_size=k, stride=1, padding=k//2),
                nn.BatchNorm1d(out_ch),
                nn.ReLU(),
                nn.MaxPool1d(kernel_size=5, stride=2, padding=2)
                #nn.Dropout(0.4)
            )

        self.backbone = nn.Sequential(
            block(20, 512, 5),
            block(512, 512, 5),
            block(512, 256, 5),
            block(256, 256, 3),
            block(256, 128, 3),
        )

        self.pool = nn.AdaptiveAvgPool1d(1)

        self.classifier = nn.Sequential(
            nn.Flatten(),           
            nn.Linear(128, 512),
            nn.ReLU(),
            nn.BatchNorm1d(512),
            #nn.Dropout(0.6),
            nn.Linear(512, num_classes) 
        )

    def forward(self, x):
        x = self.backbone(x)
        x = self.pool(x)
        x = self.classifier(x)
        return x



MODEL_CONFIGS = {
    "RAVDESS (8-class)": {
        "num_classes": 8,
        "labels": ["Neutral","Calm","Happy","Sad","Angry","Fearful","Disgust","Surprised"],
        "checkpoint": os.path.join(os.path.dirname(os.path.abspath(__file__)), "ravdess_ser1dcnn.pth"),
    },
    "CREMA-D (6-class)": {
        "num_classes": 6,
        "labels": ["Angry","Disgust","Fear","Happy","Neutral","Sad"],  
        "checkpoint": os.path.join(os.path.dirname(os.path.abspath(__file__)),"cremad_ser1dcnn.pth"),  
    }
}


def load_wave(path):
    wave, _ = librosa.load(path, mono=True, sr=22050, duration=2.5)
    target_len = int(22050 * 2.5)
    if len(wave) < target_len:
        wave = np.pad(wave, (0, target_len - len(wave)))
    else:
        wave = wave[:target_len]
    return wave


def wave_to_mfcc(wave):
    mfcc = librosa.feature.mfcc(y=wave, sr=22050, n_mfcc=20, n_fft=2048, hop_length=512)
    return mfcc


def load_model(checkpoint_path, num_classes, device):
    model = SER1DCNN(num_classes=num_classes).to(device)
    ckpt = torch.load(checkpoint_path, map_location=device)

    # 支援：你存 checkpoint dict 或純 state_dict
    if isinstance(ckpt, dict) and "model_state_dict" in ckpt:
        model.load_state_dict(ckpt["model_state_dict"])
    else:
        model.load_state_dict(ckpt)

    model.eval()
    return model


class SERGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SER GUI (RAVDESS 8-class / CREMA-D 6-class)")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.audio_path = None
        self.model = None
        self.current_cfg = None

        # --- Top: model selection + load
        frm_top = tk.Frame(root)
        frm_top.pack(fill="x", padx=10, pady=8)

        tk.Label(frm_top, text=f"Device: {self.device}").pack(side="left")

        tk.Label(frm_top, text="   Choose Model:").pack(side="left", padx=8)
        self.model_choice = tk.StringVar(value="RAVDESS (8-class)")
        ttk.Combobox(
            frm_top,
            textvariable=self.model_choice,
            values=list(MODEL_CONFIGS.keys()),
            width=18,
            state="readonly"
        ).pack(side="left")

        self.ckpt_var = tk.StringVar(value=MODEL_CONFIGS[self.model_choice.get()]["checkpoint"])
        self.model_choice.trace_add("write", self._on_model_change)

        #tk.Label(frm_top, text="   Checkpoint:").pack(side="left", padx=8)
        #tk.Entry(frm_top, textvariable=self.ckpt_var, width=35).pack(side="left")

        tk.Button(frm_top, text="Load Model", command=self.on_load_model).pack(side="left", padx=8)

        self.status_var = tk.StringVar(value="Model: NOT loaded")
        tk.Label(frm_top, textvariable=self.status_var).pack(side="left", padx=8)

        # --- Mid: audio choose + predict
        frm_mid = tk.Frame(root)
        frm_mid.pack(fill="x", padx=10, pady=6)

        tk.Button(frm_mid, text="Choose Audio", command=self.on_choose_audio).pack(side="left")
        self.audio_var = tk.StringVar(value="No file selected")
        tk.Label(frm_mid, textvariable=self.audio_var).pack(side="left", padx=8)

        tk.Button(frm_mid, text="Predict", command=self.on_predict).pack(side="left", padx=10)

        self.pred_var = tk.StringVar(value="Prediction: -")
        tk.Label(frm_mid, textvariable=self.pred_var, font=("Arial", 14)).pack(side="left", padx=10)

        # --- Bottom: probs + plots
        frm_bottom = tk.Frame(root)
        frm_bottom.pack(fill="both", expand=True, padx=10, pady=8)

        # left: probs text
        self.text = tk.Text(frm_bottom, width=30)
        self.text.pack(side="left", fill="y")
        self.text.insert("end", "Probabilities will appear here.\n")

        # right: plots
        frm_plots = tk.Frame(frm_bottom)
        frm_plots.pack(side="left", fill="both", expand=True, padx=10)

        self.fig = plt.Figure(figsize=(8, 4.5), dpi=100)
        self.ax_wave = self.fig.add_subplot(2, 1, 1)
        self.ax_mfcc = self.fig.add_subplot(2, 1, 2)

        self.canvas = FigureCanvasTkAgg(self.fig, master=frm_plots)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.cbar = None
        self._reset_plots()

    def _on_model_change(self, *_):
        cfg = MODEL_CONFIGS[self.model_choice.get()]
        self.ckpt_var.set(cfg["checkpoint"])
        self.status_var.set("Model: NOT loaded")
        self.model = None
        self.current_cfg = None

    def _reset_plots(self):
        if getattr(self, "cbar", None) is not None:
            self.cbar.remove()
            self.cbar = None
        
        self.ax_wave.clear()
        self.ax_wave.set_title("Waveform")
        self.ax_wave.set_xlabel("Time (s)")
        self.ax_wave.set_ylabel("Amplitude")

        self.ax_mfcc.clear()
        self.ax_mfcc.set_title("MFCC")
        self.ax_mfcc.set_xlabel("Time")
        self.ax_mfcc.set_ylabel("MFCC coeff")

        self.fig.tight_layout()
        self.canvas.draw()

    def on_choose_audio(self):
        path = filedialog.askopenfilename(
            title="Select audio file",
            filetypes=[("Audio files", "*.wav *.mp3 *.flac *.ogg"), ("All files", "*.*")]
        )
        if path:
            self.audio_path = path
            self.audio_var.set(os.path.basename(path))
            self._reset_plots()

    def on_load_model(self):
        cfg = MODEL_CONFIGS[self.model_choice.get()]
        ckpt = self.ckpt_var.get().strip()
        if not os.path.exists(ckpt):
            messagebox.showerror("Error", f"Checkpoint not found:\n{ckpt}")
            return
        try:
            self.model = load_model(ckpt, cfg["num_classes"], self.device)
            self.current_cfg = cfg
            self.status_var.set(f"Model loaded  ({self.model_choice.get()})")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load model:\n{e}")

    @torch.no_grad()
    def on_predict(self):
        if self.model is None or self.current_cfg is None:
            messagebox.showwarning("Warning", "Please load a model first.")
            return
        if not self.audio_path or not os.path.exists(self.audio_path):
            messagebox.showwarning("Warning", "Please choose an audio file first.")
            return

        cfg = self.current_cfg

        # 1) preprocess
        wave = load_wave(self.audio_path)
        mfcc = wave_to_mfcc(wave)  # (20,T)

        X = torch.tensor(mfcc[None, ...], dtype=torch.float32).to(self.device)  # (1,20,T)

        # 2) forward
        logits = self.model(X)
        probs = torch.softmax(logits, dim=1).cpu().numpy()[0]  # (C,)

        labels = cfg["labels"]
        pred_idx = int(np.argmax(probs))
        self.pred_var.set(f"Prediction: {labels[pred_idx]}")

        # 3) show probs
        self.text.delete("1.0", "end")
        for i, name in enumerate(labels):
            self.text.insert("end", f"{name:10s}: {probs[i]:.4f}\n")

        # 4) plot waveform
        self.ax_wave.clear()
        t = np.arange(len(wave)) /22050
        self.ax_wave.plot(t, wave)
        self.ax_wave.set_title("Waveform")
        self.ax_wave.set_xlabel("Time (s)")
        self.ax_wave.set_ylabel("Amplitude")

        # 5) plot MFCC (heatmap)
        self.ax_mfcc.clear()
        img = librosa.display.specshow(mfcc, x_axis="time", sr=22050,
                                       hop_length=512, ax=self.ax_mfcc)
        self.ax_mfcc.set_title("MFCC (n_mfcc=20)")
        self.ax_mfcc.set_ylabel("MFCC coeff")


        if self.cbar is not None:
            try:
               if (hasattr(self.cbar, "ax")
                    and self.cbar.ax is not None
                    and self.cbar.ax in self.fig.axes):
                    self.cbar.remove()
            except Exception:                pass
            finally:
                self.cbar = None


        self.cbar = self.fig.colorbar(img, ax=self.ax_mfcc, format="%+2.0f")

        self.fig.tight_layout()
        self.canvas.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = SERGUI(root)
    root.mainloop()

import os
import librosa
import numpy as np
#%%
mode = "RAVDESS" #"CREMAD"
NOISE = 0.001
SHIFT_STEP = 0.5
#%%
if mode == "RAVDESS":
    emotion_map = {
        1: "neutral",
        2: "calm",
        3: "happy",
        4: "sad",
        5: "angry",
        6: "fearful",
        7: "disgust",
        8: "surprised"
    }
    num_classes=8
#%%
## load data
RAVDESS_PATH =  os.path.join(os.path.dirname(os.path.abspath(__file__)), "Audio_Speech_Actors_01-24")
def parse_emotion_from_filename(filename):
    parts = filename.split("-")
    emotion_id = int(parts[2])
    return emotion_id

def load_ravdess_files(root=RAVDESS_PATH):
    wav_paths = []
    labels = []

    for actor_folder in sorted(os.listdir(root)):
        folder_path = os.path.join(root, actor_folder)
        #print(folder_path)
        if not os.path.isdir(folder_path):
            continue

        for file in os.listdir(folder_path):
            if file.endswith(".wav"):
                full_path = os.path.join(actor_folder, file)
                wav_paths.append(full_path)

                emotion = parse_emotion_from_filename(file)
                labels.append(emotion)

    return wav_paths, labels

#%%
if mode == "RAVDESS":
    paths, labels=load_ravdess_files()
#%%
emotion_map_C = {}
if mode == "CREMAD":
    emotion_map_C = {
        "ANG": 1,
        "DIS": 2,
        "FEA": 3,
        "HAP": 4,
        "NEU": 5,
        "SAD": 6
    }
    num_classes=6
#%%
CREAMD_PATH =  os.path.join(os.path.dirname(os.path.abspath(__file__)), "AudioWAV")
def parse_emotion_from_filename_C(filename):
    parts = filename.split("_")
    emotion_id = emotion_map_C[parts[2]]
    return emotion_id

def load_creamd_files(root=CREAMD_PATH):
    wav_paths = []
    labels = []

    for file in os.listdir(root):
        if file.endswith(".wav"):
            wav_paths.append(file)

            emotion = parse_emotion_from_filename_C(file)
            labels.append(emotion)

    return wav_paths, labels
#%%
if mode == "CREMAD":
    paths, labels=load_creamd_files()
#%%
TARGET_LEN = int(2.5 * 22050)
def wav2mfcc(file_paths,  root): # O 
    waves = []
    wave, sr = librosa.load(os.path.join(root, file_paths), mono=True, sr=22050, duration=2.5) 
    if len(wave) < TARGET_LEN:
        wave=np.pad(wave, (0, TARGET_LEN - len(wave)))
    else: wave=wave[:TARGET_LEN]
    mfcc = librosa.feature.mfcc(y=wave, sr=22050, n_mfcc=20, n_fft=2048, hop_length=512)
    waves.append(mfcc)
    w_a = wave + NOISE * np.random.randn(len(wave))
    mfcc = librosa.feature.mfcc(y=w_a, sr=22050, n_mfcc=20, n_fft=2048, hop_length=512)
    waves.append(mfcc)
    w_a = librosa.effects.pitch_shift(wave, sr=sr, n_steps=SHIFT_STEP)
    mfcc = librosa.feature.mfcc(y=w_a, sr=22050, n_mfcc=20, n_fft=2048, hop_length=512)
    waves.append(mfcc)
    return waves

if mode == "RAVDESS":
    ROOT_P = RAVDESS_PATH
if mode == "CREMAD":
    ROOT_P = CREAMD_PATH
arg_wav = []
arg_lab = []
for path, L in zip(paths, labels):
    w = wav2mfcc(path, ROOT_P)
    arg_wav.extend(w)
    arg_lab.extend([L]*3)
print(len(arg_wav), len(arg_lab))  
print(arg_wav[0].shape)   
#%%
import matplotlib.pyplot as plt
librosa.display.specshow(arg_wav[2], x_axis="time", sr=22050,hop_length=512)
#librosa.display.waveshow(arg_wav[0], sr = 22050)
plt.show()
#%%
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import TensorDataset, DataLoader

X = torch.tensor(np.stack(arg_wav), dtype=torch.float32)   
y = torch.tensor(np.array(arg_lab) - 1, dtype=torch.long)
print(X.shape, y.shape)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

train_loader = DataLoader(TensorDataset(X_train, y_train), batch_size=64, shuffle=True)
test_loader  = DataLoader(TensorDataset(X_test, y_test), batch_size=64, shuffle=False)

print(len(X_train), len(X_test))

#%%
import torch.nn as nn

class SER1DCNN(nn.Module):
    def __init__(self, num_classes):
        super().__init__()

        def block(in_ch, out_ch, k):
            return nn.Sequential(
                nn.Conv1d(in_ch, out_ch, kernel_size=k, stride=1, padding=k//2),
                nn.BatchNorm1d(out_ch),
                nn.ReLU(),
                nn.MaxPool1d(kernel_size=5, stride=2, padding=2)  
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
            nn.Linear(512, num_classes) 
        )

    def forward(self, x):
        x = self.backbone(x)
        x = self.pool(x)
        x = self.classifier(x)
        return x
#%%
import os
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"

import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score

device = "cuda" if torch.cuda.is_available() else "cpu"

model = SER1DCNN(num_classes=num_classes).to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.0001, weight_decay=5e-4)

EPOCHS = 50

best_test_acc = 0.0
best_epoch = 0
save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "best_ser1dcnn.pth")
train_losses, test_losses = [], []
train_accs, test_accs = [], []

for epoch in range(1, EPOCHS + 1):
    # ---- train ----
    model.train()
    total_loss = 0.0
    y_true, y_pred = [], []

    for Xb, yb in train_loader:
        Xb, yb = Xb.to(device), yb.to(device)

        logits = model(Xb)
        loss = criterion(logits, yb)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        pred = logits.argmax(dim=1)

        y_true.extend(yb.detach().cpu().numpy())
        y_pred.extend(pred.detach().cpu().numpy())

    train_loss = total_loss / len(train_loader)
    train_acc = accuracy_score(y_true, y_pred)

    # ---- eval ----
    model.eval()
    total_loss = 0.0
    y_true, y_pred = [], []

    with torch.no_grad():
        for Xb, yb in test_loader:
            Xb, yb = Xb.to(device), yb.to(device)
            logits = model(Xb)
            loss = criterion(logits, yb)

            total_loss += loss.item()
            pred = logits.argmax(dim=1)

            y_true.extend(yb.detach().cpu().numpy())
            y_pred.extend(pred.detach().cpu().numpy())

    test_loss = total_loss / len(test_loader)
    test_acc = accuracy_score(y_true, y_pred)
    
    print(f"Epoch {epoch:02d}/{EPOCHS} | "
          f"train loss {train_loss:.4f} acc {train_acc:.4f} | "
          f"test loss {test_loss:.4f} acc {test_acc:.4f}")
    
    if test_acc > best_test_acc:
        best_test_acc = test_acc
        best_epoch = epoch

        torch.save({
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "test_acc": test_acc,
            "test_loss": test_loss
        }, save_path)

        print(f" Saved best model at epoch {epoch} "
              f"(test acc = {test_acc:.4f})")
    train_losses.append(train_loss); test_losses.append(test_loss)
    train_accs.append(train_acc);   test_accs.append(test_acc)

#%%
import matplotlib.pyplot as plt
epochs = range(1, EPOCHS+1)

plt.figure(figsize=(10,4))
plt.subplot(1,2,1)
plt.plot(epochs, train_losses,color = "red", label='training Loss')
plt.plot(epochs, test_losses,color = "green", label='testing Loss')
plt.title('Loss Curve')
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.legend()

plt.subplot(1,2,2)
plt.plot(epochs, train_accs, color = "red", label='training Accurancy')
plt.plot(epochs, test_accs,color = "green", label='testing Accurancy')
plt.title('Accuracy Curve')
plt.xlabel('Epoch')
plt.ylabel('Accuracy')
plt.legend()

plt.tight_layout()
plt.show()
#%%
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
cm = confusion_matrix(y_true, y_pred)
if mode == "RAVDESS":
    D_label=[
         "Neutral","Calm","Happy","Sad",
         "Angry","Fearful","Disgust","Surprised"
     ]
    TITLE = "Confusion Matrix for SER (RAVDESS)"
if mode == "CREMAD":
    D_label=[ "angry", "disgust", "fear",
        "happy", "neutral", "sad"]
    TITLE = "Confusion Matrix for SER (CREMAD)"
disp = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=D_label
)
disp.plot(cmap="Blues", xticks_rotation=45)
plt.title(TITLE)
plt.show()
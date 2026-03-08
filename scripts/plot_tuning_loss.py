# plot_tuning_loss.py
import re
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Baca file log
log_file = 'tuning_lstm.log'
data = []

with open(log_file, 'r') as f:
    lines = f.readlines()

# Pola regex untuk menangkap parameter dan loss
param_pattern = r"Mencoba ({.*?}), seq_length=(\d+)"
loss_pattern = r"Val loss: ([\d\.]+)"

current_params = None
current_seq = None

for line in lines:
    # Cari baris parameter
    match_param = re.search(param_pattern, line)
    if match_param:
        param_str = match_param.group(1)
        seq = int(match_param.group(2))
        # Ubah string parameter jadi dictionary
        param_dict = eval(param_str)  # aman karena dari log sendiri
        param_dict['seq_length'] = seq
        current_params = param_dict
    # Cari baris loss
    match_loss = re.search(loss_pattern, line)
    if match_loss and current_params is not None:
        loss = float(match_loss.group(1))
        data.append({**current_params, 'loss': loss})
        current_params = None  # reset

# Buat DataFrame
df = pd.DataFrame(data)
if df.empty:
    print("Tidak ada data loss ditemukan. Pastikan tuning sudah berjalan dan log tersimpan.")
    exit()

# Urutkan berdasarkan loss terendah
df_sorted = df.sort_values('loss')
print("Top 5 kombinasi terbaik:")
print(df_sorted.head(5)[['epochs', 'learning_rate', 'hidden_dim', 'num_layers', 'dropout', 'seq_length', 'loss']])

# Plot loss untuk setiap kombinasi (urut berdasarkan indeks)
plt.figure(figsize=(12, 6))
plt.plot(df.index, df['loss'], 'o-', markersize=3)
plt.xlabel('Kombinasi ke-')
plt.ylabel('Validation Loss')
plt.title('Loss selama Tuning LSTM')
plt.grid(True)
plt.tight_layout()
plt.savefig('tuning_loss.png')
plt.show()

# Plot loss berdasarkan parameter tertentu (misal learning rate)
plt.figure(figsize=(12, 6))
for lr in df['learning_rate'].unique():
    subset = df[df['learning_rate'] == lr]
    plt.plot(subset.index, subset['loss'], 'o-', label=f'lr={lr}', markersize=3)
plt.xlabel('Kombinasi ke-')
plt.ylabel('Validation Loss')
plt.title('Loss berdasarkan Learning Rate')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig('tuning_loss_by_lr.png')
plt.show()

print("\nGrafik disimpan sebagai tuning_loss.png dan tuning_loss_by_lr.png")
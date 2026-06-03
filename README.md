# 📌 BERT-LSTM for Sentiment Analysis  

This repository contains an implementation of a **modified BERT architecture** where the standard Transformer encoder layers are augmented with **LSTM units**.  
Unlike the traditional approach of adding an LSTM *after* BERT embeddings, we **integrated LSTM directly inside the encoder layers**, allowing sequential dependencies to interact with self-attention.  

We train and evaluate this hybrid model on benchmark sentiment datasets like **IMDB** and **TweetEval**.  

---

## 🚀 Features  
- Modified **BERT encoder** with LSTM integration  
- Supports **IMDB** and **TweetEval** datasets  
- Training & evaluation scripts with **PyTorch + HuggingFace Transformers**  
- Reports **Accuracy, F1-score, and confusion matrix**  

---

## 🏗️ Architecture  
---
```Text → BERT Tokenizer → Modified BERT (Self-Attention + LSTM) → [CLS] → Classifier → Sentiment```


🔹 Key difference from vanilla BERT:  
- Transformer layers are **redefined** to include an **LSTM block** inside the encoder.  
- This hybrid combines **global context (attention)** and **sequential recurrence (LSTM)**.  

---

## 📊 Datasets  
- **[IMDB Movie Reviews](https://ai.stanford.edu/~amaas/data/sentiment/)** – binary sentiment (positive/negative)  
- **[TweetEval](https://github.com/cardiffnlp/tweeteval)** – Twitter sentiment classification  

---

## ⚙️ Installation  

Clone the repo and install dependencies:  
```bash
git clone https://github.com/<your-username>/bert-lstm-sentiment.git
cd bert-lstm-sentiment
pip install -r requirements.txt
```

## 🔧 Training

IMDB:
```bash
python train.py --dataset imdb --epochs 3 --batch_size 16
```

TweetEval:
```bash
python train.py --dataset tweeteval --epochs 3 --batch_size 32
```

## 🧪 Evaluation
```bash
python test.py --dataset imdb --checkpoint path/to/model.ckpt
```


🙌 Acknowledgements

- [HuggingFace Transformers](https://github.com/huggingface/transformers)
- [IMDB Dataset](https://ai.stanford.edu/~amaas/data/sentiment/)
- [TweetEval Dataset](https://github.com/cardiffnlp/tweeteval)




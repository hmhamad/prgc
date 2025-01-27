# To reproduce the results on pytorch enabled environment
git clone https://github.com/hy-struggle/PRGC.git
cd PRGC/

# Download bert model, config and vocab
mkdir -p pretrain_models/bert_base_cased
cd pretrain_models/bert_base_cased && \
    wget https://huggingface.co/bert-base-cased/resolve/main/config.json &&  mv config.json bert_config.json && \
    wget https://huggingface.co/bert-base-cased/resolve/main/vocab.txt  && \
    wget https://huggingface.co/bert-base-cased/resolve/main/pytorch_model.bin && \
    cd ../..

# Install dependencies
python3 -m venv prgc-venv
source prgc-venv/bin/activate
pip3 install torch transformers tqdm pandas

# Begin training
python train.py --ex_index=1 --epoch_num=100 --device_id=2 --corpus_type=WebNLG --ensure_corres --ensure_rel --rel_threshold 0.1 --corres_threshold 0.5
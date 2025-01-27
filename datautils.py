from torch.utils.data import Dataset, RandomSampler
import torch
import os
import json

def reltypes2id_10K():
    pathtoTypes = os.path.join(os.sep, os.path.dirname(__file__), 'data', '10K', '10K_types.json')
    with open(pathtoTypes, "r") as file:
        data = json.load(file)
    rel2id  = [{}]
    for idx,(relk,relv) in enumerate(data['relations'].items()):
        rel2id[0][relk] = idx
    pathtoRel2id = os.path.join(os.sep, os.path.dirname(__file__), 'data4PRGC', '10K', 'rel2id.json')
    with open(pathtoRel2id, "w") as file:
        json.dump(rel2id,file)

def ChangeDataFormat():
    file_names = {'10K_train.json':'train_triples.json','10K_dev.json':'val_triples.json','10K_test.json':'test_triples.json'}
    pathto10K = os.path.join(os.sep, os.path.dirname(__file__), 'data', '10K')
    pathtoPRGC = os.path.join(os.sep, os.path.dirname(__file__), 'data4PRGC', '10K')
    for (orig_file,new_file) in file_names.items():
        pathtoOrig = os.path.join(os.sep,pathto10K,orig_file)
        pathtoNew = os.path.join(os.sep,pathtoPRGC,new_file)
        with open(pathtoOrig, "r") as file:
            dataorig = json.load(file)
        datanew = [{} for i in range(len(dataorig))]
        for idx,example in enumerate(dataorig):
            tokens = example['tokens']
            entities = example['entities']
            datanew[idx]['text'] = ' '.join(tokens)
            datanew[idx]['triple_list'] = []
            for rel in example['relations']:
                rel_type = rel['type']
                head_ent = ' '.join(tokens[entities[rel['head']]['start']:entities[rel['head']]['end']])
                tail_ent = ' '.join(tokens[entities[rel['tail']]['start']:entities[rel['tail']]['end']])
                datanew[idx]['triple_list'].append([head_ent,rel_type,tail_ent])
        with open(pathtoNew, "w") as file:
            json.dump(datanew,file)

def ReadData(Dataset, type):
    type = type + '.json' if type == 'rel2id' else type + '_triples.json'
    pathtoData = os.path.join(os.sep, os.path.dirname(__file__), 'data4PRGC', Dataset)
    pathtoFile = os.path.join(os.sep, pathtoData, type)
    with open(pathtoFile, "r") as file:
        data = json.load(file)
    if type == 'rel2id.json':
        return data[0]
    else:
        text = [];
        labels = []
        for example in data:
            text.append(example['text']);
            labels.append(example['triple_list'])
        return text, labels

def FindHeadIdx(ent_ids, input_ids):
    for ii in range(len(input_ids)):
        if (input_ids[ii:ii+len(ent_ids)] == ent_ids):
            return ii
    return -1

def GetEntRange(input_ids, ent_str, tokenizer):
    ent_ids = tokenizer.convert_tokens_to_ids(tokenizer.tokenize(ent_str))
    head_idx = FindHeadIdx(ent_ids, input_ids.tolist())
    range_ent = (head_idx, head_idx + len(ent_ids) - 1)
    return range_ent

def GetTrainFeatures(rel2id, str_labels, input_ids, attention_mask, tokenizer, seq_len):
    rel_num = len(rel2id)

    labels_list = []
    tot_ex_counter = 0
    tot_ex_counter_lagged = 0
    for idx1, example in enumerate(str_labels):
        relation_labels = torch.zeros(rel_num, dtype=torch.long)
        corres_matrix = torch.zeros(size=(seq_len, seq_len), dtype=torch.long)
        sentence_rel = []
        for label in example:
            subj_seq_tag = torch.zeros(seq_len, dtype=torch.long)
            obj_seq_tag = torch.zeros(seq_len, dtype=torch.long)
            target_rel = rel2id[label[1]]

            subj_token_ids = torch.tensor(tokenizer.convert_tokens_to_ids(tokenizer.tokenize(label[0])))
            subj_head_idx = FindHeadIdx(subj_token_ids.tolist(), input_ids[idx1].tolist())
            subj_seq_tag[subj_head_idx] = 1
            subj_seq_tag[(subj_head_idx + 1):(subj_head_idx + len(subj_token_ids))] = 2

            relation_labels[rel2id[label[1]]] = 1

            obj_token_ids = torch.tensor(tokenizer.convert_tokens_to_ids(tokenizer.tokenize(label[2])))
            obj_head_idx = FindHeadIdx(obj_token_ids.tolist(), input_ids[idx1].tolist())
            obj_seq_tag[obj_head_idx] = 1
            obj_seq_tag[(obj_head_idx + 1):(obj_head_idx + len(obj_token_ids))] = 2

            corres_matrix[subj_head_idx, obj_head_idx] = 1

            if (target_rel in sentence_rel):
                # Same relation occured twice in sentence for different entities, don't add as new train example,
                # only extend set of entity tags (model should detect this relation and all corresponding subj/obj tags)
                idx_rel_example = tot_ex_counter - len(sentence_rel) + sentence_rel.index(target_rel)
                labels_list[idx_rel_example]['subj_seq_tag'] = torch.where((labels_list[idx_rel_example]['subj_seq_tag']==0) & (subj_seq_tag!=0),
                                                                           subj_seq_tag, labels_list[idx_rel_example]['subj_seq_tag'])
                labels_list[idx_rel_example]['obj_seq_tag'] = torch.where((labels_list[idx_rel_example]['obj_seq_tag']==0) & (obj_seq_tag!=0),
                                                                           obj_seq_tag, labels_list[idx_rel_example]['obj_seq_tag'])
            else:
                # new train example for this target relation
                labels_list.append({})
                labels_list[tot_ex_counter]['input_ids'] = input_ids[idx1]
                labels_list[tot_ex_counter]['attention_mask'] = attention_mask[idx1]
                labels_list[tot_ex_counter]['target_rel'] = target_rel
                labels_list[tot_ex_counter]['subj_seq_tag'] = subj_seq_tag 
                labels_list[tot_ex_counter]['obj_seq_tag'] = obj_seq_tag 
                tot_ex_counter += 1

            sentence_rel.append(target_rel)

        for idx in range(len(set(sentence_rel))):
            labels_list[tot_ex_counter_lagged]['corres_matrix'] = corres_matrix
            labels_list[tot_ex_counter_lagged]['relation_labels'] = relation_labels
            tot_ex_counter_lagged += 1

    return labels_list

def GetValFeatures(rel2id, str_labels, input_ids, attention_mask, tokenizer, seq_len):
    labels_list = [{} for i in range(len(str_labels))]

    for idx1, triples in enumerate(str_labels):
        triples_list = []
        for triple in triples:
            subj_ent_range = GetEntRange(input_ids[idx1], triple[0], tokenizer)
            rel_id = rel2id[triple[1]]
            obj_ent_range = GetEntRange(input_ids[idx1], triple[2], tokenizer)
            triples_list.append((subj_ent_range, rel_id, obj_ent_range))
        labels_list[idx1]['input_ids'] = input_ids[idx1]
        labels_list[idx1]['attention_mask'] = attention_mask[idx1]
        labels_list[idx1]['triples'] = triples_list

    return labels_list

class TrainDataset(Dataset):
    def __init__(self, text, labels, rel2id, tokenizer, max_plm_seq_len):
        self.text = text
        self.labels = labels
        self.rel2id = rel2id
        self.tokenizer = tokenizer
        self.encoded_text = self.tokenizer(
            text,
            add_special_tokens=False,
            padding=True,
            max_length=max_plm_seq_len,
            truncation=True,
            return_token_type_ids=False,
            return_attention_mask=True,
            return_tensors='pt',
        )
        self.seq_len = self.encoded_text['input_ids'].shape[1]
        self.labels = GetTrainFeatures(rel2id, labels, self.encoded_text['input_ids'], self.encoded_text['attention_mask'], self.tokenizer, self.seq_len)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            'input_ids': self.labels[idx]['input_ids'],
            'attention_mask': self.labels[idx]['attention_mask'],
            'subj_seq_tag': self.labels[idx]['subj_seq_tag'],
            'obj_seq_tag': self.labels[idx]['obj_seq_tag'],
            'target_rel': self.labels[idx]['target_rel'],
            'corres_matrix': self.labels[idx]['corres_matrix'],
            'relation_labels': self.labels[idx]['relation_labels']
        }

class ValDataset(Dataset):
    def __init__(self, text, labels, rel2id, tokenizer, seq_len):
        self.text = text
        self.labels = labels
        self.rel2id = rel2id
        self.tokenizer = tokenizer
        self.seq_len = seq_len
        self.encoded_text = self.tokenizer(
            text,
            add_special_tokens=False,
            padding='max_length',
            max_length=seq_len,
            truncation=True,
            return_token_type_ids=False,
            return_attention_mask=True,
            return_tensors='pt',
        )
        self.labels = GetValFeatures(rel2id, labels, self.encoded_text['input_ids'], self.encoded_text['attention_mask'], self.tokenizer, self.seq_len)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.labels[idx]['input_ids'], self.labels[idx]['attention_mask'], self.labels[idx]['triples']


if __name__ == "__main__":
    reltypes2id_10K()
    ChangeDataFormat()
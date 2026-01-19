import random
import warnings
import csv
import ast
import spacy
from spacy.util import minibatch, compounding
from spacy.training import Example

nlp = spacy.load("/home/o/resources/en_core_web_lg_ner1")

ner = nlp.get_pipe("ner")
ner.add_label("BAND")

other_pipes = [pipe for pipe in nlp.pipe_names if pipe != "ner"]

TRAIN_DATA = []

with open('train_data1.csv', 'r', newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        text = row[0]
        entities = []
        for entity_str in row[1:]:
            entity_tuple = ast.literal_eval(entity_str)
            start, end, label = entity_tuple
            entities.append((start, end, label))
        TRAIN_DATA.append((text, {"entities": entities}))

with nlp.disable_pipes(*other_pipes), warnings.catch_warnings():
    # show warnings for misaligned entity spans once
    warnings.filterwarnings("once", category=UserWarning, module='spacy')

    for itn in range(10):
        random.shuffle(TRAIN_DATA)
        losses = {}
        # batch up the examples using spaCy's minibatch
        batches = minibatch(TRAIN_DATA, size=compounding(4.0, 32.0, 1.001))
        for batch in batches:
            texts, annotations = zip(*batch)
            examples = [Example.from_dict(nlp.make_doc(text), annotations) for text, annotations in zip(texts, annotations)]
            nlp.update(examples, drop=0.5, losses=losses)
        print("Losses", losses)

nlp.to_disk("/home/o/resources/en_core_web_lg_ner2")

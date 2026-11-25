"""Real CPU retrieval + synthetic language outputs; never runs final15 inference."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from planning_lab.backend import Response
from planning_lab.common import ROOT, atomic_json, canonical, digest, read_json, read_jsonl, write_jsonl
from planning_lab.rag_runtime import Session, BudgetedQwen, BudgetExceeded
from planning_lab.rag_retrieval import BM25Retriever, RetrieverFactory
from planning_lab.rag_methods import METHODS
from planning_lab.rag_support import check_support, stop_gate
from planning_lab import rag_runner as runner
from planning_lab import rag_evaluation as evaluation

CONFIG=dict(read_json(ROOT/'configs/rag_development.json'),retriever='bm25')
PLAN={'nodes':[
    {'id':'q1','question':'Who directed Example Film?','dependencies':{},'answer_type':'person'},
    {'id':'q2','question':'Where was {{q1}} born?','dependencies':{'q1':'person'},'answer_type':'place'}], 'final':'q2'}


def fixture(qid='synthetic-one'):
    texts=['Example Film was directed by Dana.',
           'Example Film director film directed Example Film review.',
           'Example Film director film directed Example Film production.',
           "Dana's birthplace is Bruma."]+['Unrelated document number '+str(i) for i in range(6)]
    passages=[dict(index=i,title='Document '+str(i),sentences=[text],sentence_ids=[0],text=text)
              for i,text in enumerate(texts)]
    return dict(question_id=qid,question='Where was the director of Example Film born?',question_type='bridge',
                role='development',passages=passages,frozen_plan=copy.deepcopy(PLAN),structure_valid=True,
                plan_debit={'llm_calls':1,'total_tokens':100})


def plan_record(q):
    return dict(plan=q['frozen_plan'],plan_sha256=digest(q['frozen_plan']),status='valid' if q['structure_valid'] else 'invalid',
                budget_debit=q['plan_debit'])


class ScriptBackend:
    identity={'backend':'synthetic_rag_software_test','live_inference':False}
    load_seconds=0.
    def __init__(self,mode='normal'):
        self.mode,self.messages=mode,[]
    def count_tokens(self,messages):return 100
    def check_context(self,prompt,output):pass
    def generate(self,messages,maximum,seed):
        self.messages.append(messages)
        if self.mode=='model_error':raise RuntimeError('Synthetic interrupted generate')
        user=messages[-1]['content']
        if 'Decompose Question into a small typed rooted TREE' in messages[0]['content']:
            result=copy.deepcopy(PLAN)
        elif user.startswith('RAG_SUPPORT_CHECK_V1'):
            data=json.loads(user.rsplit('\n',1)[1])
            supported=self.mode not in {'reject_support','unsupported_goal'} or (self.mode=='unsupported_goal' and data['scope']!='original_goal')
            support=[dict(ref=ref,quote=data['evidence'][ref]['sentence']) for ref in data['candidate_refs']]
            if self.mode=='fabricate_quote':support[0]['quote']='THIS SENTENCE IS NOT IN THE EVIDENCE'
            result=dict(supported=supported,entity='Dana',property='birthplace' if data['candidate']=='Bruma' else 'director',
                        value=data['candidate'],support=support,conflict=False,missing_query='' if supported else 'Dana birthplace',
                        reason='Synthetic verdict for software test')
        elif user.startswith('RAG_FINAL_CITATIONS_V1'):
            data=json.loads(user.rsplit('\n',1)[1])
            result={'refs':[ref for ref,e in data['evidence'].items() if 'directed by Dana' in e['sentence'] or 'birthplace is Bruma' in e['sentence']]}
        elif user.startswith('Decide whether the evidence contains all facts'):
            result={'is_sufficient':'birthplace is Bruma' in user,'follow_up_query':'Dana birthplace'}
        elif user.startswith('Audit cached Bindings'):
            result={'invalid':[]}
        elif user.startswith('Answer Node using only Evidence'):
            node=user.split('\nNode:\n',1)[1].split('\nAnswer type:',1)[0]
            if node.startswith('Who directed'):
                result={'answer':'Dana','refs':['0:0'],'need':''}
            elif 'birthplace is Bruma' in user:
                result={'answer':'Bruma','refs':['3:0'],'need':''}
            else:result={'answer':'','refs':[],'need':'Dana birthplace'}
        elif messages[0]['content'].startswith('Use only the supplied evidence. Return a factual answer'):
            return Response('Bruma' if 'birthplace is Bruma' in user else '',100,2,.001)
        else:raise AssertionError('Unexpected synthetic backend prompt: '+user[:100])
        return Response(canonical(result),100,20,.001)



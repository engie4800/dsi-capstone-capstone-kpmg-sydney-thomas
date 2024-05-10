import openai
import pandas as pd     
from langchain.chains import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI
from typing import Dict, List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from FlagEmbedding.bge_m3 import BGEM3FlagModel
from prompts_3layer import LAYER_ONE_PROMPT, LAYER_TWO_PROMPT, LAYER_THREE_PROMPT, QA_PROMPT
from langchain.chains.llm import LLMChain
from langchain.prompts import PromptTemplate
from prompts_3layer import node_properties_query, rel_properties_query, rel_query, schema_text

API_KEY = "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"

class TPT:
    
    def __init__(self, graphDB: Neo4jGraph):
        self.graphDB = graphDB
        self.Tool1 = ThreeLayerGPT(self.graphDB)
        self.Tool2 = BaseGPT(self.graphDB)
        self.model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
        
    def __call__(self, file, export=True):
        self._loadTestSet(file)
        self._getAnswer()
        self._getSimilarity("3-layer GPT Answer")
        self._getSimilarity("Base GPT Answer")
        if export:
            self.testSet.to_csv("Evaluate Result.csv", index=False)
        
    def _loadTestSet(self, file):
        self.testSet = pd.read_csv(file)
        
    def _getAnswer(self):
        self.testSet["3-layer GPT Answer"] = "None"
        self.testSet["Base GPT Answer"] = "None"
        for i in range(self.testSet.shape[0]):
            message = self.testSet["Prompts"][i]
            self.testSet["3-layer GPT Answer"][i] = self.Tool1(message)
            self.testSet["Base GPT Answer"][i] = self.Tool2(message)
    
    def _getSimilarity(self, col):
        col_name = col + " Score"
        self.testSet[col_name] = "None"
        for i in range(self.testSet.shape[0]):
            true_answer = [self.testSet["True Answer"][i]]
            generated_answer = [self.testSet[col][i]]
            sentence_pairs = [[m, n] for m in true_answer for n in generated_answer]
            res = self.model.compute_score(sentence_pairs,
                    max_passage_length=128,
                    weights_for_different_modes=[0.4, 0.2, 0.4])  
            self.testSet[col_name][i] = res['colbert+sparse+dense'][0]
            
class ThreeLayerGPT:
    
    def __init__(self, graphDB: Neo4jGraph):
        self.prompts = [LAYER_ONE_PROMPT, LAYER_TWO_PROMPT, LAYER_THREE_PROMPT]
        self.chat1 = ChatOpenAI(api_key=API_KEY, temperature=0)
        self.chat2 = ChatOpenAI(api_key=API_KEY, temperature=0)
        self.chat3 = ChatOpenAI(api_key=API_KEY, temperature=0)
        self.chat4 = ChatOpenAI(api_key=API_KEY, temperature=0)
        self.graphDB = graphDB
        
    def __call__(self, message_input):
        return self.getResult(message_input)
    
    def _getSchema(self):
        node_props = self.graphDB.query(node_properties_query)
        rel_props = self.graphDB.query(rel_properties_query)
        rels = self.graphDB.query(rel_query)
        node_props = [value for d in node_props for value in d.values()]
        rel_props = [value for d in rel_props for value in d.values()]
        rels = [value for d in rels for value in d.values()]
        schema = schema_text(node_props, rel_props, rels)
        return schema
        
    def _distillation(self, message):
        messages = [
        SystemMessage(
            content=self.prompts[0]
        ),
        HumanMessage(
            content=message
        )]
        response = self.chat1.invoke(messages)
        content = eval(response.dict()['content'])
        return content        
        
    def _queryLogic(self, message):
        messages = [
        SystemMessage(
            content=self.prompts[1]
        ),
        HumanMessage(
            content=message
        )]
        response = self.chat2.invoke(messages)
        content = response.dict()['content']
        return content  
    
    def _queryGeneration(self, message):
        messages = [
        SystemMessage(
            content=self.prompts[2]
        ),
        HumanMessage(
            content=message
        )]
        response = self.chat3.invoke(messages)
        content = response.dict()['content']
        return content  
    
    def _generateAnswer(self, message):
        human_prompt_template = PromptTemplate.from_template(
        template= "The original question is {question}, the previous LLM has generate intermediate result {answer}")

        human_prompt = human_prompt_template.format(
            question =  message["question"], 
            answer = message["answer"]
        )
        
        PROMPT = QA_PROMPT + "\n" + self._getSchema()

        messages = [
            SystemMessage(
                content=PROMPT
            ),
            HumanMessage(
                content= human_prompt
            )]
        
        response = self.chat4.invoke(messages)
        content = response.dict()['content']
        return content           
    
    def getResult(self, message_input):
        response = self._distillation(message_input)
        message_layer1 = "User Requirement:" + str(message_input) + "\n" + "Query Logic and Relationship:" + str(response)
        response = self._queryLogic(message_layer1)
        updatemessage = "User Requirement:" + str(message_input) + "\n" + "Query Logic Extraction:" + str(response)
        query = self._queryGeneration(updatemessage) 
        data = self.graphDB.query(query)  
        user_message = {"question": message_input, "answer": data}
        final_output = self._generateAnswer(user_message)
        return final_output

class BaseGPT:
    
    def __init__(self, graphDB: Neo4jGraph):
        self.graphDB = graphDB
        self.chain = GraphCypherQAChain.from_llm(
            llm = ChatOpenAI(temperature=0, api_key=API_KEY),
            graph=self.graphDB, verbose=False
        )
    
    def __call__(self, message):
        try:
            res = self.chain(message)
        except:
            return "Error Query"
        return res['result']
    
if __name__ == "__main__":
    graph = Neo4jGraph(url="neo4j+s://9014d857.databases.neo4j.io", username="neo4j", password="RYYNymC3Bug5n9Il-ke_RPAHKkIQNlP5zujB-B8H8w8")
    file = "KPMG_test_set.csv"
    testTool = TPT(graph)
    testTool(file)

      
    
    
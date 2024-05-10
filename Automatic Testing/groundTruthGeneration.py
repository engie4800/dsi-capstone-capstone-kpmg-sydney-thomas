import pandas as pd   
from prompts_3layer import QA_PROMPT
from langchain.chains import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.prompts import PromptTemplate
from tqdm import tqdm

API_KEY = "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"

data = pd.read_csv("KPMG Test Set.csv")

chat = ChatOpenAI(api_key=API_KEY, temperature=0)

def generateAnswer(message):
    human_prompt_template = PromptTemplate.from_template(
    template= "The original question is {question}, the previous LLM has generate intermediate result {answer}")

    human_prompt = human_prompt_template.format(
        question =  message["question"], 
        answer = message["answer"]
    )

    messages = [
        SystemMessage(
            content = """
            I will give you the question and the answer, please orchestrate the answer based on the question to process a natural human way answer
"""
        ),
        HumanMessage(
            content= human_prompt
        )]
    
    response = chat.invoke(messages)
    content = response.dict()['content']
    return content 

message_inputs = [{"question": message_input, "answer": data} for message_input, data in zip(data["Prompts"], data["Ground Truth"])]
data["True Answer"] = "0"

for i in tqdm(range(data.shape[0])):
    data["True Answer"][i] = generateAnswer(message_inputs[i])

if __name__ == "__main__":
    data.to_csv("KPMG_test_set.csv", index=False)
import os
from dotenv import load_dotenv
load_dotenv()

import os
import argparse
import time
import requests
import pathlib
from datetime import datetime
from bs4 import BeautifulSoup

from langchain.utilities import GoogleSerperAPIWrapper
from langchain.chat_models import ChatOpenAI
from langchain.chains.llm import LLMChain
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA, RetrievalQAWithSourcesChain
from langchain.prompts import PromptTemplate
from langchain.experimental.plan_and_execute.schema import (
    Plan,
    PlanOutputParser,
    Step,
)

from utils.scrapers.base import Scraper
from utils.threatintel import handle_pdf
from utils.MemoryRetrievalChain import MemoryRetrievalChain

import tiktoken
tokenizer = tiktoken.get_encoding("cl100k_base")


class BlogSectionParser(PlanOutputParser):
  def parse(self, text: str) -> Plan:
    steps = [Step(value=v) for v in text.split('SECTION:\n')[1:]]
    return Plan(steps=steps)


class GeneralScraper(Scraper):
  blog_url = None
  source = None
  base_url = None

  def __init__(self):
    self.driver = self.get_selenium()


  def scrape_post(self, url=None):
    self.driver.get(url)
    time.sleep(5)
    html = self.driver.execute_script("return document.getElementsByTagName('html')[0].innerHTML")

    soup = BeautifulSoup(html, 'lxml')

    return soup
  

def get_top_n_search(query, n):
  search = GoogleSerperAPIWrapper()
  search_result = search.results(query)
  
  return search_result['organic'][:n]


def text_splitter(text, n, tokenizer):
  chunks = []
  chunk = ''
  sentences = [s.strip().replace('\n', ' ') for s in text.split('.')]
  for s in sentences:
    # start new chunk
    if chunk == '':
      chunk = s
    else:
      chunk = chunk + ' ' + s
    
    chunk_len = len(tokenizer.encode(chunk))
    if chunk_len >= 0.9*n:
      chunks.append(chunk)
      chunk = ''

  if chunk != '':
    chunks.append(chunk)
  
  return chunks


def scrape_and_chunk_pdf(url, n, tokenizer):
  r = requests.get(url)
  with open('tmp.pdf', 'wb') as pdf:
    pdf.write(r.content)

  return handle_pdf(pathlib.Path('tmp.pdf'), n, tokenizer)


def scrape_and_chunk(url, token_size, tokenizer):
  if url.endswith('.pdf'):
    chunks, pages, meta = scrape_and_chunk_pdf(url, 100, tokenizer)
    
    return chunks
  else:
    scraper = GeneralScraper()
    soup = scraper.scrape_post(url)

    for script in soup(["script", "style"]):
      script.extract()

    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    results = "\n".join(chunk for chunk in chunks if chunk)

    return text_splitter(results, token_size, tokenizer)
  

def get_ephemeral_vecdb(chunks, metadata):
  embeddings = OpenAIEmbeddings()
  
  return FAISS.from_texts(chunks, embeddings, metadatas=[metadata for _ in range(len(chunks))])


def get_sources_context(query, llm, retriever):
  vec_qa = RetrievalQAWithSourcesChain.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)
  res = vec_qa({'question': query})
  
  return '\n'.join(['source: {}'.format(res['sources']), res['answer']])


def get_context(query, llm, retriever):
  vec_qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)
  res = vec_qa({'query': query})
  
  return res['result']


def get_question_chain(llm):
  question_template = """You are a Senior Content writer for a top tier alternative investment platform, Goldfinch. Goldfinch focuses on making private credit accessible to a broad audience.
  You should consider the audience to be an educated lay person, with some, but not much finance background.

  Suppose you've been given the following task:
  {input}

  What questions would you want to ask and answer in order to complete the above task?

  Please make a list of 1-3 such questions.

  QUESTIONS:
  """

  input_vars = ['input']

  question_prompt = PromptTemplate(
      input_variables=input_vars, template=question_template
  )

  return LLMChain(llm=llm, prompt=question_prompt, verbose=True)


def get_library_retriever():
  embeddings = OpenAIEmbeddings()

  # Load from Local
  db = FAISS.load_local("vecstore_backup", embeddings)
  return db.as_retriever(search_kwargs={"k": 4})


def get_section_chain(llm):
    _section_draft_prompt = """You are a Senior Content writer for a top tier alternative investment platform, Goldfinch. Goldfinch focuses on making private credit accessible to a broad audience.
    You should consider the audience to be an educated lay person, with some, but not much finance background.

    You're writing a new blog post with several SECTIONS. You're going to write one SECTION of the blog post at a time.
    Below is the SECTION you're writing now. Pay attention to the Heading, Length, and Guidance for this SECTION, but please 
    don't repeat them in your response.

    Some CONTEXT is provided below, but you probably have additional information. If the information below
    is not related to this SECTION, you can ignore it.

    LIBRARY CONTEXT:
    {library}

    SEARCH CONTEXT:
    {search}

    Is there additional relevant information not captured in the above CONTEXT?
    Include that additional information in your response.
    Feel free to use tables, bullet points, or lists in your response.

    Respond using markdown.

    Be sure to cite the sources you reference using footnotes.

    Write in the style of Michael Lewis and the Economist.

    And, hey, don't forget to be casual and friendly... occasionaly funny!

    SECTION
    {input}
    """

    input_vars = ['library', 'search', 'input']
    section_draft_prompt = PromptTemplate(
        input_variables=input_vars, template=_section_draft_prompt
    )

    return LLMChain(llm=llm, prompt=section_draft_prompt, verbose=True)




def main(outline):
  llm = ChatOpenAI(temperature=1.0)
  
  section_parser = BlogSectionParser()
  sections = section_parser.parse(outline)

  library_retriever = get_library_retriever()
  question_chain = get_question_chain(llm)
  section_chain = get_section_chain(llm)

  os.makedirs('new_post/sections', exist_ok=True)
  # Loop through each section
  for idx, _section in enumerate(sections.steps):
    section = _section.value
    print(section)

    # Get questions for this section
    questions = question_chain({'input': section})
    print(questions['text'])

    search_context = []
    library_context = []
    # Loop through questions
    for _query in questions['text'].split('\n'):
      query = _query.strip()[3:]
      print(query)

      # library context
      library_query_context = get_context(query, llm, library_retriever)
      library_context.append(library_query_context)

      # top n search context
      top_n_search_results = get_top_n_search(query, 3)

      # Look through top n urls
      for _url in top_n_search_results:
        try:
          url = _url['link']
          print(url)

          chunks = scrape_and_chunk(url, 100, tokenizer)
          vec_db = get_ephemeral_vecdb(chunks, {'source': url})
          src_context = get_sources_context(query, llm, vec_db.as_retriever())
          search_context.append(src_context)
        except:
          print('Issue with {}'.format(url))
          continue
      
    full_library = '\n'.join(library_context)
    full_search = '\n'.join(search_context)
    

    _prompt = section_chain.prompt.format_prompt(**{
      'input': section,
      'search': full_search,
      'library': full_library
    })

    # Write each section with MemoryRetrievalChain
    res = section_chain({
      'input': section,
      'search': full_search,
      'library': full_library
    })


    with open(f'new_post/sections/section_prompt{idx}.txt', 'w') as f:
        #f.write(f'{heading}\n')
        f.write(_prompt.text)
    
    with open(f'new_post/sections/section{idx}.txt', 'w') as f:
        #f.write(f'{heading}\n')
        f.write(res['text'])

    with open('new_post/blog.txt', 'a') as f:
        #f.write(f'\n\n{heading}\n')
        f.write(res['text'])
        f.write('\n\n')



if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--outline_path', type=str)
      
  args, _ = parser.parse_known_args()
  print(args.outline_path)

  outline = open(args.outline_path).read()

  main(outline)
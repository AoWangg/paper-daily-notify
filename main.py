import json
from venv import logger
import arxiv
import argparse
import os
import requests
import datetime
import re
from time import sleep
from tqdm import trange
from openai import OpenAI

from construct_message import render_message

def get_paper_code_url(paper:arxiv.Result) -> str:
    retry_num = 5
    while retry_num > 0:
        try:
            paper_list = requests.get(f'https://paperswithcode.com/api/v1/papers/?arxiv_id={paper.arxiv_id}').json()
            break
        except:
            sleep(1)
            retry_num -= 1
            if retry_num == 0:
                return None
    
    if paper_list.get('count',0) == 0:
        return None
    paper_id = paper_list['results'][0]['id']
    retry_num = 5
    while retry_num > 0:
        try:
            repo_list = requests.get(f'https://paperswithcode.com/api/v1/papers/{paper_id}/repositories/').json()
            break
        except:
            sleep(1)
            retry_num -= 1
            if retry_num == 0:
                return None
    if repo_list.get('count',0) == 0:
        return None
    return repo_list['results'][0]['url']

def get_arxiv_paper_from_web(query:str, start:datetime.datetime, end:datetime.datetime) -> list[arxiv.Result]:
    cats = re.findall(r'cat:(\w+)?\.\w+?', query)
    cats = set(cats)
    query_list = query.split(' ')
    real_query = []
    for q in query_list:
        if q in ["OR","AND","ANDNOT"]:
            if real_query[-1] in ["OR","AND","ANDNOT"]:
                #This means previous filter is skipped
                real_query.pop()
            real_query.append(q)
        if q.startswith("cat:"):
            real_query.append(q)

    if real_query[-1] in ["OR","AND","ANDNOT"]:
        real_query.pop()

    logger.info(f"Retrieving arXiv papers from {start} to {end} with {' '.join(real_query)}. Other query filters are ignored.")
    all_paper_ids = []
    for cat in cats:
        url = f"https://arxiv.org/list/{cat}/new" #! This only retrieves the latest papers submitted in yesterday
        response = requests.get(url)
        if response.status_code != 200:
            logger.warning(f"Cannot retrieve papers from {url}.")
            continue
        html = response.text
        paper_ids = re.findall(r'arXiv:(\d+\.\d+)', html)
        all_paper_ids.extend(paper_ids)

    def is_valid(paper:arxiv.Result):
        published_date = paper.published
        if not (published_date < end and published_date >= start):
            return False
        stack = []
        op_dict = {
            "AND": lambda x,y: x and y,
            "OR": lambda x,y: x or y,
            "ANDNOT": lambda x,y: x and not y
        }
        for q in real_query:
            if q.startswith("cat:"):
                if len(stack) == 0:
                    stack.append(q[4:] in paper.categories)
                else:
                    op = stack.pop()
                    x = stack.pop()
                    assert op in ["AND","OR","ANDNOT"], f"Invalid query {query}"
                    assert x in [True,False], f"Invalid query {query}"
                    stack.append(op_dict[op](x,q[4:] in paper.categories))
            elif q in ["AND","OR","ANDNOT"]:
                stack.append(q)
        assert len(stack) == 1 and (stack[0] in [True, False]), f"Invalid query {query}"
        return stack.pop()
    
    client = arxiv.Client()
    results = []
    for i in trange(0,len(all_paper_ids),50,desc="Filtering papers"):
        search = arxiv.Search(id_list=all_paper_ids[i:i+50])
        for i in client.results(search):
            if is_valid(i):
                i.arxiv_id = re.sub(r'v\d+$', '', i.get_short_id())
                i.code_url = get_paper_code_url(i)
                results.append(i)
    return results 


def get_arxiv_paper(query:str, start:datetime.datetime, end:datetime.datetime, debug:bool=False, llm:OpenAI=None) -> list[arxiv.Result]:
    client = arxiv.Client()
    search = arxiv.Search(query=query, sort_by=arxiv.SortCriterion.SubmittedDate)
    retry_num = 5
    if not debug:
        while retry_num > 0:
            papers = []
            try:
                for i in client.results(search):
                    print(i.title)
                    published_date = i.published
                    if published_date < end and published_date >= start:
                        i.arxiv_id = re.sub(r'v\d+$', '', i.get_short_id())
                        i.code_url = get_paper_code_url(i)
                        papers.append(i)
                    elif published_date < start:
                        break
                break
            except Exception as e:
                logger.warning(f'Got error: {e}. Try again...')
                sleep(180)
                retry_num -= 1
                if retry_num == 0:
                    raise e
        if len(papers) == 0:
            logger.warning("Cannot retrieve new papers from arXiv API. Try to retrieve from web page.")
            papers = get_arxiv_paper_from_web(query, start, end)
    else:
        logger.debug("Retrieve 5 arxiv papers regardless of the date.")
        while retry_num > 0:
            papers = []
            try:
                for i in client.results(search):
                    print(i.title)
                    i.arxiv_id = re.sub(r'v\d+$', '', i.get_short_id())
                    i.code_url = get_paper_code_url(i)
                    papers.append(i)
                    if len(papers) == 5:
                        break
                break
            except Exception as e:
                logger.warning(f'Got error: {e}. Try again...')
                sleep(180)
                retry_num -= 1
                if retry_num == 0:
                    raise e
    for p in papers:
        title_cn_response = llm.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "user", "content": "这是这篇文章的英文标题：" + p.title + "，请用中文翻译一下。只需要输出翻译后的标题，不需要任何其他内容。"},
            ],
        )
        p.title_cn = title_cn_response.choices[0].message.content
        
        summary_cn_response = llm.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "user", "content": "这是这篇文章的英文摘要：" + p.summary + "，请用中文翻译一下。只需要输出翻译后的摘要，不需要任何其他内容。"},
            ],
        )
        p.summary_cn = summary_cn_response.choices[0].message.content
        
    return papers

def send_to_feishu_webhook(webhook_url: str, message: dict):
    headers = {"Content-type": "application/json", "charset":"utf-8"}
    msg_encode=json.dumps(message,ensure_ascii=True).encode("utf-8")
    response = requests.post(webhook_url, data=msg_encode, headers=headers)
    if response.status_code != 200:
        logger.error(f"Failed to send message to Feishu: {response.text}")

def get_env(key:str,default=None):
    v = os.environ.get(key)
    if v == '' or v is None:
        return default
    return v


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Recommender system for academic papers')
    parser.add_argument('--arxiv_query', type=str, help='Arxiv search query', default=get_env('ARXIV_QUERY'))
    parser.add_argument('--lark_webhook', type=str, help='Lark webhook url', default=get_env('LARK_WEBHOOK'))
    parser.add_argument('--max_paper_num', type=int, help='Maximum number of papers to recommend',default=get_env('MAX_PAPER_NUM',100))
    parser.add_argument(
        "--openai_api_key",
        type=str,
        help="OpenAI API key",
        default=get_env("OPENAI_API_KEY"),
    )
    parser.add_argument(
        "--openai_api_base",
        type=str,
        help="OpenAI API base URL",
        default=get_env("OPENAI_API_BASE", "https://api.openai.com/v1"),
    )
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    args = parser.parse_args()
    
    llm = OpenAI(
        api_key= args.openai_api_key,
        base_url=args.openai_api_base,
    )

    search_query = args.arxiv_query
    logger.info(f"Searching for papers with query: {search_query}")
    
    today = datetime.datetime.now(tz=datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - datetime.timedelta(days=1)
    
    papers = get_arxiv_paper(search_query, yesterday, today, debug=True, llm=llm)
    
    message = render_message(papers)
    logger.info("Sending message to Feishu...")
    send_to_feishu_webhook(args.lark_webhook, message)
    
    logger.info("Done.")
       
import arxiv

def render_message(papers:list[arxiv.Result]):
    if len(papers) == 0 :
        return {"msg_type":"text","content":{"text":"今日无新论文"}}
    
    elements = []
    elements.append({
        "tag": "div",
        "text": {
            "content": "**最新论文🎉** \n",
            "tag": "lark_md"
        }
    })

    for p in papers:
        summary = p.summary
        
        authors = [a.name for a in p.authors[:5]]
        authors = ', '.join(authors)
        if len(p.authors) > 5:
            authors += ', ...'
            
        publish_time = p.published
        
        elements.append({
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "default",
            "columns": [
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 4,
                    "vertical_align": "top",
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": f"**{p.title}**\n<font color='grey'>英文摘要: {summary}</font>"
                        },
                        {
                            "tag": "markdown",
                            "content": f"**{p.title_cn}**\n<font color='grey'>中文摘要: {p.summary_cn}</font>"
                        },
                        {
                            "tag": "column_set",
                            "flex_mode": "none",
                            "background_style": "grey",
                            "columns": [
                                {
                                    "tag": "column",
                                    "width": "weighted",
                                    "weight": 1,
                                    "vertical_align": "top",
                                    "elements": [
                                        {
                                            "tag": "markdown",
                                            "content": f"*{publish_time}*\n<font color='grey'>发表时间</font>",
                                            "text_align": "center"
                                        }
                                    ]
                                },
                                {
                                    "tag": "column",
                                    "width": "weighted",
                                    "weight": 1,
                                    "vertical_align": "top",
                                    "elements": [
                                        {
                                            "tag": "markdown",
                                            "content": f"**<font color='red'>{authors}</font>**\n<font color='grey'>作者</font>",
                                            "text_align": "center"
                                        }
                                    ]
                                },
                                {
                                    "tag": "column",
                                    "width": "weighted",
                                    "weight": 1,
                                    "vertical_align": "top",
                                    "elements": [
                                        {
                                            "tag": "markdown",
                                            "content": f"{p.links[0].href}\n<font color='grey'>在线查看</font>",
                                            "text_align": "center"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        })
    
    elements.append({
        "tag": "note",
        "elements": [
            {
                "tag": "img",
                "img_key": "img_v2_8895d99e-e163-45f1-ac1d-553b30306c4g",
                "alt": {
                    "tag": "plain_text",
                    "content": ""
                }
            },
            {
                "tag": "plain_text",
                "content": "恭喜你读完了今天的所有文献！加油"
            }
        ]
    })

    return {"msg_type": "interactive", "card": {"elements": elements}}

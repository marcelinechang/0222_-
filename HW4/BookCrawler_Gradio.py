#!/usr/bin/env python
# coding: utf-8

# In[9]:


import gradio as gr
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

import jieba
import jieba.analyse

import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from community import community_louvain

import matplotlib as mpl
from matplotlib.font_manager import fontManager

import tempfile

class BookTopSalesCrawler:


    def __init__(self):
        self.BASE_URL = 'https://www.books.com.tw/web/sys_saletopb/'
        self.session = requests.Session()
        
        self.duration = ['7', '30']
        self.language = ['中文', '簡體', '外文']
        
        self.catagory = {'中文':'books','簡體':'china','外文':'fbooks'} #排行榜語言類參數對照
        self.days = {'7':'7', '30':'30'} #排行榜天數參數對照
        
        radio1 = gr.Radio(self.duration, label="天數", info="請選擇想要查看的排行榜天數")
        radio2 = gr.Radio(self.language, label="語言", info="請選擇想要查看的排行榜語言種類")
        
        self.temp_dir = tempfile.TemporaryDirectory()

    
    
    #抓取書籍內容簡介
    def fetch_content(self,page):
        response = self.session.get(page)
        
        if response.status_code not in [200,484]: #484應該是博客來的自定義代號
            print(f"{str(response.status_code)} 無法訪問書籍頁面 {page}")
            return ''
        
        soup = BeautifulSoup(response.text, 'html.parser')
    
        #有的書籍有閱讀年齡的限制，必須登入會員才可以觀看，因此這類書籍的內容簡介無法抓取，故使用空值替代
        try:
            text = soup.select_one('div.content').text
            cleaned_text = re.sub(r'[\n\u3000\xa0]+', '', text).strip() #使用正則化
            return cleaned_text
        
        except AttributeError:
            return ''

        
    #提取前十個關鍵字
    def extract_keywords(self,text):
        return jieba.analyse.extract_tags(text, topK=10) #提取前十個關鍵字


    #抓取排行榜頁面的書名、作者、售價、書籍頁面連結
    def fetch_pages(self, language, duration): #可根據輸入的語言類別與天數抓取指定頁面
        current_page = f'{self.BASE_URL}{self.catagory[self.selected_category]}/?attribute={self.days[self.selected_days]}'
        response = self.session.get(current_page)
        
        if response.status_code != 200:
            print(f"無法訪問排行榜頁面 {current_page}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for channel in soup.select('div.type02_bd-a'): #選取所有 class 為 type02_bd-a 的 div 元素
            
            #選取第一個 href 屬性含有 products 字串的 a 標籤，href 屬性值
            link = channel.select_one("a[href*=products]")['href']
            
            #選取 h4 標籤下 a 標籤的文字內容
            title = channel.select_one("h4 > a").text
            
            #選取 class 為 msg 的 ul 標籤下第一個 li 元素的文字內容，並使用正則化清理資料
            if "作者" in channel.select_one("ul.msg > li:nth-child(1)").text:
                author_text = channel.select_one("ul.msg > li:nth-child(1)").text
                author = re.sub(r'作者：?', '', author_text)
            #有些書籍沒有顯示作者，故給空值
            else:
                author = ''
            
            #選取 class 為 msg 的 ul 標籤下，class 為 price_a 的 li 元素的文字內容，並使用正則化清理資料
            price_text = channel.select_one("ul.msg > li.price_a").text
            price_match = re.search(r'(\d+)元', price_text)
            if price_match:
                price = int(price_match.group(1))
            else:
                price = None

            content = self.fetch_content(link) #呼叫抓取書籍內容簡介的Function，並產製書本簡介內容
            keywords = self.extract_keywords(content)
            self.data.append({'title': title, 'author': author, 'price': price, 'link': link, 'intro': content, 'keywords': keywords})
            
        
    
    def making_relation_graph(self, data):
        G = nx.Graph()

        for index, row in data.head(25).iterrows():
            author = row['author']
            keywords = row['keywords']

            G.add_node(author, type='author')

            for keyword in keywords:
                G.add_node(keyword, type='keyword')
                G.add_edge(author, keyword)

        fontManager.addfont('jf-openhuninn-2.0.ttf')
        mpl.rc('font', family='jf-openhuninn-2.0')

        partition = community_louvain.best_partition(G)
        community_colors = [partition[node] for node in G.nodes()]
        cmap = plt.cm.jet

        custom_colors = ["#e2e2df","#d2d2cf","#e2cfc4","#f7d9c4","#faedcb","#c9e4de","#c6def1","#dbcdf0","#f2c6de","#f9c6c9"]
        colors_with_alpha = [custom_colors[community_color % len(custom_colors)] for community_color in community_colors]

        node_sizes = [200 * G.degree(node) for node in G.nodes()]

        pos = nx.spring_layout(G, k=0.25, iterations=85, scale=2)

        fig = plt.figure(figsize=(30, 30))
        nx.draw_networkx_edges(G, pos, alpha=0.5)
        nx.draw_networkx_nodes(G, pos, node_color=colors_with_alpha, node_size=node_sizes)
        nx.draw_networkx_labels(G, pos, font_size=15, font_family='jf-openhuninn-2.0')

        plt.axis('off')

        # 生成临时文件名
        temp_filename = f"{self.temp_dir.name}/my_graph.png"

        # 将图像保存到临时文件
        fig.savefig(temp_filename, format='png', bbox_inches='tight')

        # 将临时文件名返回，方便其他函数读取图像数据
        return temp_filename

    
    def process_choices(self, duration, language):
        self.data = []
        self.selected_days = duration
        self.selected_category = language
        self.fetch_pages(duration, language)
        df = self.to_dataframe()
        img_str = self.making_relation_graph(df)
        return df, img_str

    def launch(self):
        with gr.Blocks(css="""
            .gradio-container {
                max-width: 1600px;
                margin: 0 auto;
            }
            #df_output table {
                width: 100%;
            }
            #img_output > div {
                width: 1000px;
                margin: 0 auto;
            }
        """) as demo:
            with gr.Row():
                radio1 = gr.Radio(self.duration, label="天數")
                radio2 = gr.Radio(self.language, label="語言")
            output = [gr.Dataframe(headers=["title", "author", "price", "link", "intro", 'keywords'],elem_id="df_output"),gr.Image(elem_id="df_output")]
            
            btn = gr.Button("開始爬取")
            btn.click(fn=self.process_choices, inputs=[radio1, radio2], outputs=output)

            
        demo.launch(debug=True)

    
    
    #把資料變成dataframe
    def to_dataframe(self):
        return pd.DataFrame(self.data)


#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import requests
from bs4 import BeautifulSoup
import pandas as pd
import re


class BookTopSalesCrawler:
    def __init__(self):
        self.BASE_URL = 'https://www.books.com.tw/web/sys_saletopb/'
        self.session = requests.Session()
        self.catagory = {'中文':'books','簡體':'china','外文':'fbooks'} #排行榜語言類參數對照
        self.days = {'7':'7', '30':'30'} #排行榜天數參數對照
        self.data = [] #儲存書籍資訊
        
    
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


    #抓取排行榜頁面的書名、作者、售價、書籍頁面連結
    def fetch_pages(self, language, duration): #可根據輸入的語言類別與天數抓取指定頁面
        current_page = f'{self.BASE_URL}{self.catagory[language]}/?attribute={self.days[duration]}'
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
            self.data.append({'title': title, 'author': author, 'price': price, 'link': link, 'intro': content})
            
    
    
    #把資料變成dataframe
    def to_dataframe(self):
        return pd.DataFrame(self.data)


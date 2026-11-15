"""Build HugStar's product introduction and beginner manual from shared copy.

Developer-only dependencies: docs/product/requirements.txt. PDFs use selected
beauty renders and a simplified diagram for the internal USB and BOOT button.
"""
import html
import json
import math
from pathlib import Path

import qrcode
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/product'
ASSETS=OUT/'assets'
W,H=420,595
BLUE=HexColor('#276DB3');INK=HexColor('#25445F');MUTED=HexColor('#667F92')
CREAM=HexColor('#FFF9EE');PALE=HexColor('#EDF7FF');PINK=HexColor('#FFE7F0');YELLOW=HexColor('#FFE9A8')
DATA=json.loads((OUT/'content.json').read_text(encoding='utf-8'))
pdfmetrics.registerFont(TTFont('CN','C:/Windows/Fonts/msyh.ttc',subfontIndex=0))
pdfmetrics.registerFont(TTFont('CNB','C:/Windows/Fonts/msyhbd.ttc',subfontIndex=0))
pdfmetrics.registerFontFamily('CN',normal='CN',bold='CNB',italic='CN',boldItalic='CNB')


def para(c,text,x,top,width,size=10.2,color=INK,bold=False,leading=None):
    style=ParagraphStyle('body',fontName='CNB' if bold else 'CN',fontSize=size,
                         leading=leading or size*1.6,textColor=color,wordWrap='CJK')
    p=Paragraph(html.escape(text),style);_,height=p.wrap(width,1000)
    p.drawOn(c,x,top-height)
    return top-height


def star(c,x,y,r=11,face=False):
    points=[]
    for i in range(10):
        a=math.pi/2+i*math.pi/5;d=r if i%2==0 else r*.65
        points.append((x+math.cos(a)*d,y+math.sin(a)*d))
    path=c.beginPath();path.moveTo(*points[0])
    for i in range(10):
        p0,p1,p2,p3=(points[(i+j)%10] for j in (-1,0,1,2))
        path.curveTo(p1[0]+(p2[0]-p0[0])/6,p1[1]+(p2[1]-p0[1])/6,
                     p2[0]-(p3[0]-p1[0])/6,p2[1]-(p3[1]-p1[1])/6,*p2)
    path.close();c.setFillColor(CREAM if face else YELLOW);c.setStrokeColor(BLUE);c.setLineWidth(1.3)
    c.drawPath(path,fill=1,stroke=1)
    if face:
        c.setFillColor(BLUE)
        for dx in (-r*.22,r*.22):c.roundRect(x+dx-1,y-1,2,4,1,fill=1,stroke=0)
        c.setFillColor(HexColor('#FFBCD5'))
        for dx in (-r*.44,r*.44):c.ellipse(x+dx-3,y-4,x+dx+3,y-1,fill=1,stroke=0)


def brand(c,page,total,label='新手说明书'):
    c.setFillColor(CREAM);c.rect(0,0,W,H,fill=1,stroke=0)
    c.setFillColor(PINK);c.circle(W+18,H+20,110,fill=1,stroke=0)
    c.setFillColor(PALE);c.circle(-35,50,85,fill=1,stroke=0)
    star(c,40,H-31,15,True)
    para(c,DATA['brand'],62,H-20,230,10.5,BLUE,True)
    c.setStrokeColor(HexColor('#D5E8F4'));c.setLineWidth(.6);c.line(26,29,W-26,29)
    para(c,'一代核心  /  '+label,26,23,280,7.2,MUTED)
    para(c,f'{page:02d} / {total:02d}',W-70,23,50,7.2,MUTED)


def heading(c,title,subtitle=''):
    y=para(c,title,26,H-67,W-52,23,BLUE,True,29)
    return para(c,subtitle,26,y-8,W-52,9.5,MUTED)-20


def card(c,title,body,x,top,width,fill=white,size=10.2,min_height=0):
    style=ParagraphStyle('measure',fontName='CN',fontSize=size,leading=size*1.6,wordWrap='CJK')
    p=Paragraph(html.escape(body),style);_,h=p.wrap(width-28,1000)
    height=max(min_height,h+44)
    c.setFillColor(fill);c.roundRect(x,top-height,width,height,12,fill=1,stroke=0)
    para(c,title,x+14,top-11,width-28,11,BLUE,True,16)
    para(c,body,x+14,top-32,width-28,size)
    return top-height-10


def numbered(c,steps,top):
    for n,(title,body) in enumerate(steps,1):
        c.setFillColor(PINK if n%2 else PALE);c.circle(42,top-14,16,fill=1,stroke=0)
        para(c,str(n),36,top-6,15,11,BLUE,True)
        y=para(c,title,69,top-3,W-95,12,BLUE,True)
        top=para(c,body,69,y-6,W-95,10.2)-23
    return top


def photo(c,path,x,y,w,h):
    c.drawImage(str(path),x,y,w,h,preserveAspectRatio=True,anchor='c',mask='auto')


def number_dot(c,n,x,y):
    c.setFillColor(white);c.setStrokeColor(BLUE);c.setLineWidth(.9)
    c.circle(x,y,8,fill=1,stroke=1)
    para(c,str(n),x-3,y+5.5,12,7.5,BLUE,True)


def device_views(c,top):
    y=top-162
    # Crop only the placement on the PDF page; keep the selected render intact.
    c.saveState();path=c.beginPath();path.roundRect(26,y,194,156,12);c.clipPath(path,stroke=0)
    scale=194/1086
    c.drawImage(str(ASSETS/'core-hero.png'),26,y-(1448-1220)*scale,194,1448*scale)
    c.restoreState()
    number_dot(c,1,26+670*scale,y+(1220-930)*scale)
    number_dot(c,2,26+800*scale,y+(1220-715)*scale)
    para(c,'外壳美化图 · 1 传感器口 / 2 开关',29,y-6,200,7.1,MUTED)
    c.setFillColor(PALE);c.roundRect(234,y,160,156,12,fill=1,stroke=0)
    bx,by=276,y+23
    c.setFillColor(HexColor('#334857'));c.roundRect(bx,by,76,112,6,fill=1,stroke=0)
    c.setFillColor(YELLOW)
    for i in range(8):
        for px in (bx+4,bx+72):c.circle(px,by+8+i*13.5,2,fill=1,stroke=0)
    c.setFillColor(HexColor('#9BB7CA'));c.roundRect(bx+23,by+66,30,27,3,fill=1,stroke=0)
    for dx,label in ((13,'RST'),(43,'BOOT')):
        c.setFillColor(HexColor('#D6E3EB'));c.roundRect(bx+dx,by+39,20,16,3,fill=1,stroke=0)
        c.setFillColor(HexColor('#778B9A'));c.circle(bx+dx+10,by+47,5,fill=1,stroke=0)
        para(c,label,bx+dx-1,by+36,28,5.4,white)
    c.setFillColor(HexColor('#D6E3EB'));c.roundRect(bx+23,by-2,30,26,4,fill=1,stroke=0)
    c.setFillColor(HexColor('#536C80'));c.roundRect(bx+27,by+1,22,10,3,fill=1,stroke=0)
    number_dot(c,3,bx+58,by+8)
    number_dot(c,4,bx+69,by+49)
    para(c,'主控按钮位置示意 · 必要时开盖',238,y-6,160,7.1,MUTED)


def qr(c,url,x,y,size):
    code=qrcode.QRCode(border=3,error_correction=qrcode.constants.ERROR_CORRECT_M)
    code.add_data(url);code.make(fit=True);matrix=code.get_matrix();u=size/len(matrix)
    c.setFillColor(white);c.roundRect(x-3,y-3,size+6,size+6,6,fill=1,stroke=0)
    c.setFillColor(INK)
    for row,line in enumerate(matrix):
        for col,on in enumerate(line):
            if on:c.rect(x+col*u,y+(len(matrix)-row-1)*u,u+.02,u+.02,fill=1,stroke=0)


def cover(c,manual=False):
    photo(c,ASSETS/'core-hero.png',0,20,W,560)
    star(c,40,H-31,15,True);para(c,DATA['brand'],62,H-20,240,11,BLUE,True)
    para(c,DATA['product'],26,540,360,10,BLUE)
    para(c,'第一次使用，' if manual else '把触摸，',26,509,370,27,BLUE,True,33)
    para(c,'从这里开始。' if manual else '变成一句回应。',26,473,370,27,BLUE,True,33)
    if manual:
        for i,(title,_) in enumerate(DATA['manual'][0]['steps']):
            x=26+i*124;c.setFillColor(white);c.roundRect(x,66,116,38,11,fill=1,stroke=0)
            para(c,f'{i+1}  {title}',x+11,92,96,10,BLUE,True)
        para(c,'成品核心新手指南 · '+DATA['version'],26,49,W-52,8,MUTED)
    else:
        for i,label in enumerate(('触摸回应','部位自定','互动记录')):
            x=26+i*124;c.setFillColor(white);c.roundRect(x,67,116,31,12,fill=1,stroke=0)
            para(c,label,x+21,88,90,10.5,BLUE,True)
        para(c,'开启互动，让每一次按压都有被听见的机会。',26,49,W-52,9,INK)
    para(c,'实物美化图',W-80,20,64,6.5,MUTED)


def introduction():
    path=OUT/'抱抱星_共感娃娃核心_产品介绍.pdf'
    c=canvas.Canvas(str(path),pagesize=(W,H));c.setTitle(DATA['brand']+' | 产品介绍')
    c.setAuthor('AI Doll / HugStar');cover(c);c.showPage();brand(c,2,2,'产品介绍')
    y=heading(c,'给陪伴，多一点触感。',DATA['intro'])
    for i,(title,body) in enumerate(DATA['features']):
        x=26+(i%2)*190;top=y-(i//2)*99
        card(c,title,body,x,top,178,PINK if i in (0,3) else PALE,size=9.7,min_height=87)
    y-=211
    para(c,'选择你习惯的连接方式',26,y,W-52,13,BLUE,True)
    y-=27
    for title,body in [
        ('Operit','安卓手机直连，自动同步记录；可开启触摸主动回复。'),
        ('ChatGPT / Claude','按平台添加 MCP 连接，查询记录或开始限时互动。'),
        ('DeepSeek 模型','通过支持 MCP 的客户端接入；配置在客户端中完成。')]:
        y=para(c,title,26,y,95,9.5,BLUE,True)
        y=para(c,body,126,y+15,W-152,9.1)-12
    y-=3;para(c,'八路输入 · 2.4 GHz Wi-Fi · PA2.0锁扣接口',26,y,W-52,9.5,BLUE,True)
    y=para(c,DATA['extension'],26,y-23,W-52,8.8,MUTED)
    para(c,'独立充放电模块 · 103450 / 3.7V / 2000mAh · 软硬件开源',26,y-13,W-52,8.5,MUTED)
    c.linkURL('https://github.com/SunRichardSKT/ai-doll-mcp',(26,31,W-26,53),relative=0)
    c.save();return path


def manual():
    path=OUT/'抱抱星_共感娃娃核心_新手说明书.pdf'
    c=canvas.Canvas(str(path),pagesize=(W,H));c.setTitle(DATA['brand']+' | 新手说明书')
    c.setAuthor('AI Doll / HugStar');cover(c,True);c.showPage()
    p=DATA['manual'][1];brand(c,2,6);y=heading(c,p['title'],p['subtitle'])
    device_views(c,y)
    top=y-190
    for i,(title,body) in enumerate(p['parts']):
        card(c,f'{i+1}  {title}',body,26+(i%2)*190,top-(i//2)*84,178,white,size=8.5,min_height=76)
    top-=173
    top=para(c,p['power'],26,top,W-52,9.2)
    para(c,p['care'],26,top-9,W-52,8.4,MUTED)
    c.showPage()
    p=DATA['manual'][2];brand(c,3,6);y=heading(c,p['title'],p['subtitle'])
    y=numbered(c,p['steps'],y)
    y=card(c,'记住这个顺序',p['tip'],26,y,W-52,PINK,size=9.1)
    y=para(c,p['browser'],26,y-2,W-52,8.8)
    para(c,p['hotspot'],26,y-10,W-52,8.4,MUTED)
    c.showPage()
    p=DATA['manual'][3];brand(c,4,6);y=heading(c,p['title'],p['subtitle'])
    y=para(c,p['usb'],26,y,W-52,9.3)-16
    for i,(title,body) in enumerate(p['routes']):
        y=card(c,title,body,26,y,W-52,PALE if i%2==0 else white,size=9.1)
    para(c,p['deepseek'],26,y-1,W-52,8.5,MUTED)
    c.showPage()
    p=DATA['manual'][4];brand(c,5,6);y=heading(c,p['title'],p['subtitle'])
    y=numbered(c,p['steps'],y)
    y=card(c,'只记录，也可以',p['sync'],26,y,W-52,PALE,size=9.2)
    y=para(c,p['queue'],26,y-1,W-52,9.1)-12
    para(c,p['offline'],26,y,W-52,8.5,MUTED)
    c.showPage()
    p=DATA['manual'][5];brand(c,6,6);y=heading(c,p['title'],p['subtitle'])
    for title,body in p['faq']:
        y=para(c,title,26,y,W-52,10.2,BLUE,True)
        y=para(c,body,26,y-4,W-52,9.1)-15
    y=para(c,p['closing'],26,y-2,W-52,10.2,BLUE,True)-15
    url='https://github.com/SunRichardSKT/ai-doll-mcp'
    qr(c,url,29,43,57)
    para(c,'完整教程、下载与开源资料',102,96,285,10,BLUE,True)
    para(c,'扫码或点击这里，按所用平台查看详细步骤。',102,75,285,8.6,MUTED)
    c.linkURL(url,(26,40,W-26,104),relative=0)
    c.save();return path


def markdown():
    intro=['# '+DATA['brand']+'｜'+DATA['product'],'',DATA['tagline'],'',DATA['intro'],'']
    intro+=['## '+a+'\n\n'+b+'\n' for a,b in DATA['features']]
    intro+=['## 基础配置','']+[f'- {a}：{b}' for a,b in DATA['specs']]+['',DATA['extension'],'',
             'AI回复需要完成相应客户端连接并开启互动。官方MCP聊天按需查询或限时互动；Operit可开启触摸主动回复。',
             '', '[平台连接说明](../integrations/OFFICIAL_CLIENTS.md) · [项目源码](https://github.com/SunRichardSKT/ai-doll-mcp)']
    (OUT/'产品介绍.md').write_text('\n'.join(intro)+'\n',encoding='utf-8',newline='\n')
    lines=['# 抱抱星共感娃娃核心｜新手说明书','',DATA['version']+'。面向已装好的成品；配套文件与界面版本保持一致。','']
    for n,page in enumerate(DATA['manual'],1):
        lines += [f'## {n}. '+page['title'],'',page['subtitle'],'']
        for key,value in page.items():
            if key in ('title','subtitle'):continue
            if isinstance(value,list):
                lines += [f'{i}. **{a}**：{b}' for i,(a,b) in enumerate(value,1)]+['']
            else:lines += [value,'']
    lines+=['[完整平台连接](../integrations/OFFICIAL_CLIENTS.md) · [完整教程](../README.md)']
    (OUT/'新手说明书.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':
    markdown()
    for path in (introduction(),manual()):print(path)

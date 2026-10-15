"""Render explanatory release illustrations locally with Pillow.

No game assets, screenshots, personal paths or remote services are used.
Run from any directory: python docs/screenshots/render_release_1_1_0.py
"""
from pathlib import Path
import os
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
W, H, S = 1600, 1080, 2
BG = '#0b1622'
PANEL = '#132531'
INK = '#edf6f7'
MUTED = '#9cb4c1'
TEAL = '#69d1c0'
BORDER = '#294553'
GOLD = '#d6b775'
FONTS = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'

def font(n, bold=False):
    name = 'segoeuib.ttf' if bold else 'segoeui.ttf'
    path = FONTS / name
    try:
        return ImageFont.truetype(str(path), n*S)
    except OSError:
        return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', n*S)

class Canvas:
    def __init__(self):
        self.im = Image.new('RGB', (W*S,H*S), BG)
        self.d = ImageDraw.Draw(self.im)
        for y in range(H*S):
            t=y/(H*S)
            self.d.line((0,y,W*S,y), fill=(int(10+6*t),int(22+14*t),int(34+12*t)))
        for x in range(0,W+H,100):
            self.line((x-H,H,x,0), '#142b38', 1)
    def rect(self, box, fill, radius=16, outline=None, width=1):
        self.d.rounded_rectangle(tuple(round(v*S) for v in box), radius*S, fill=fill, outline=outline, width=width*S)
    def line(self, box, fill=BORDER, width=2):
        self.d.line(tuple(round(v*S) for v in box), fill=fill, width=width*S)
    def text(self, xy, txt, size=24, color=INK, bold=False, anchor=None):
        self.d.text((xy[0]*S,xy[1]*S), txt, font=font(size,bold), fill=color, anchor=anchor)
    def circle(self, xy, r, fill, outline=None, width=2):
        self.d.ellipse(((xy[0]-r)*S,(xy[1]-r)*S,(xy[0]+r)*S,(xy[1]+r)*S),fill=fill,outline=outline,width=width*S)
    def pill(self, box, txt, fill='#193b40', color=TEAL, size=19):
        self.rect(box,fill,18)
        self.text(((box[0]+box[2])/2,(box[1]+box[3])/2-1),txt,size,color,True,'mm')
    def header(self, title, subtitle):
        self.rect((60,57,66,183),TEAL,3)
        self.text((90,53),'AZURIK MODDING HUB',21,MUTED,True)
        self.text((88,91),title,47,INK,True)
        self.text((91,158),subtitle,24,MUTED)
        self.pill((1350,61,1538,108),'VERSION 1.1.0',size=19)
    def footer(self):
        self.line((60,995,1540,995),BORDER,1)
        self.text((62,1017),'EXPLANATORY DIAGRAM  ·  NOT AN IN-GAME SCREENSHOT',19,MUTED,True)
        self.text((1537,1028),'Azurik Debug Menu',19,MUTED,False,'rm')
    def save(self,name):
        self.im.resize((W,H),Image.Resampling.LANCZOS).save(OUT/name,optimize=True)

def native_menu():
    c=Canvas()
    c.header('Explore the native menu','A guide to the in-game menu structure and its new tools.')
    c.rect((60,226,650,957),PANEL,22,BORDER)
    c.text((94,257),'IN-GAME MENU STRUCTURE',18,TEAL,True)
    c.text((94,295),'Debug Menu - 1.1.0',33,GOLD,True)
    c.line((94,354,616,354))
    rows=['Change level...','Play Movie...','Game state...','Freecam','Text boxes','Oracles']
    for i, label in enumerate(rows):
        y=382+i*72
        if label in ('Game state...','Text boxes','Oracles'):
            c.rect((84,y-3,626,y+58),'#1b3641',10)
        c.text((104,y+7),f'{i+1:02}',18,MUTED,True)
        c.text((150,y+1),label,29,INK,True)
        c.text((596,y+18),'›',30,TEAL,False,'mm')
    c.line((94,841,616,841))
    c.text((96,868),'Six root entries',24,TEAL,True)
    c.text((96,907),'English labels throughout the menu',21,MUTED)

    x=690
    c.rect((x,226,1540,416),PANEL,22,BORDER)
    c.pill((720,251,852,285),'GAME STATE',size=16)
    c.text((720,307),'Keys',30,INK,True)
    c.text((720,357),'20 key types, grouped by realm',24,MUTED)
    c.pill((1265,308,1508,357),'5 INVENTORY SLOTS',size=17)
    c.text((1268,375),'Existing slots are respected',17,MUTED)

    c.rect((x,438,1540,731),PANEL,22,BORDER)
    c.pill((720,463,855,497),'TEXT BOXES',size=16)
    c.text((720,514),'67 popup sequences',30,INK,True)
    c.line((720,566,1507,566))
    c.text((722,588),'Seals',24,TEAL,True)
    c.text((1507,589),'6 text panels',23,MUTED,False,'ra')
    c.text((722,641),'Fragment and seal messages',24,TEAL,True)
    c.text((722,681),'9 additional entries — voice only',22,MUTED)

    c.rect((x,753,1540,957),PANEL,22,BORDER)
    c.pill((720,778,828,812),'ORACLES',size=16)
    c.text((720,835),'Spoken guidance',30,INK,True)
    c.text((720,886),'Realm introductions',24,MUTED)
    c.text((1125,886),'Other spoken hints',24,MUTED)
    c.footer()
    c.save('native-menu-1.1.0.png')

def arrow(c,x1,x2,y):
    c.line((x1,y,x2,y),TEAL,3)
    c.line((x2-11,y-8,x2,y),TEAL,3)
    c.line((x2-11,y+8,x2,y),TEAL,3)

def controls():
    c=Canvas()
    c.header('Open, explore, return','A short button sequence opens the native debug menu during gameplay.')
    c.rect((60,226,1540,563),PANEL,22,BORDER)
    c.text((94,249),'OPEN OR REOPEN THE MENU',18,TEAL,True)
    c.pill((1230,247,1505,289),'WITHIN 1 SECOND',size=19)
    positions=[(307,'WHITE','#f4f6f3','#1a2b32'),(799,'A','#75c85a','#112a14'),(1291,'B','#d3655c','#381715')]
    for i,(x,label,fill,ink) in enumerate(positions):
        c.circle((x,376),58,fill,'#748c95' if i==0 else fill,2)
        c.text((x,376),label,20 if i==0 else 39,ink,True,'mm')
        c.text((x,455),f'{i+1}  Press {label}',23,INK,True,'mm')
    arrow(c,391,715,376)
    arrow(c,883,1207,376)
    c.text((800,513),'You may release each button between steps. Release all three before repeating.',23,MUTED,False,'mm')

    c.rect((60,586,790,760),PANEL,18,BORDER)
    c.text((90,610),'CLOSE → OPEN AGAIN',19,TEAL,True)
    c.text((90,648),'Use the same sequence after closing.',25,INK,True)
    c.text((90,694),'The retained native menu is reused.',22,MUTED)
    c.text((90,723),'No cheat-code reset is required.',22,MUTED)
    c.rect((812,586,1540,760),PANEL,18,BORDER)
    c.text((842,610),'ALTERNATIVE SHORTCUT',19,TEAL,True)
    c.text((842,651),'L3 + START',30,INK,True)
    c.text((842,704),'Open the menu with the alternative chord.',22,MUTED)

    c.text((62,786),'FREECAM',18,TEAL,True)
    for box,key,description in [
        ((60,822,538,913),'START','Confirm the Freecam menu entry'),
        ((557,822,1035,913),'Y','Hide or show the HUD'),
        ((1054,822,1540,913),'WHITE / BACK','Exit and restore player controls')]:
        c.rect(box,PANEL,14,BORDER)
        c.text((box[0]+23,box[1]+13),key,23,TEAL,True)
        c.text((box[0]+23,box[1]+54),description,19,INK)
    c.text((800,958),'World updates continue · Azurik’s movement controls are disabled · Idle animations continue',22,MUTED,False,'mm')
    c.footer()
    c.save('freecam-controls-1.1.0.png')

if __name__=='__main__':
    native_menu()
    controls()
    print('Rendered native-menu-1.1.0.png and freecam-controls-1.1.0.png')

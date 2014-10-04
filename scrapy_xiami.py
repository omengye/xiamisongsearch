# -*- coding: utf-8 -*-

import os
import tornado.web
import tornado.options
import tornado.httpserver
import tornado.ioloop
import tornado.gen
import tornado.httpclient
import bs4
import json
from tornado.options import define, options
define("port", default=8000, help="run on the given port", type=int)

def page_url(key=None, PageNo=1):
    if key is not None:
        url = 'http://www.xiami.com/web/search-songs?key=' + unicode(key) + '&limit=5&page=' + str(PageNo)
        return url.replace(' ','+')

def get_albuminfo(content):
    album_body = bs4.BeautifulSoup(content)
    rank_and_votes = album_body.findAll('div', {'id': 'album_rank'})[0]
    album_rank = rank_and_votes.em.string # 专辑得分
    album_votes = rank_and_votes.i.string # 评价人数(少于10人按10人计算)
    lang_com_date = album_body.findAll('td', {'valign': 'top'})
    lang = lang_com_date[3].string  # 专辑语种
    com = lang_com_date[5].a.string # 唱片公司
    date = lang_com_date[7].string  # 发行时间
    return album_rank, album_votes, lang, com, date

def get_songinfo(content):
    song_soup = bs4.BeautifulSoup(content)
    albums_info = song_soup.findAll('table', {'id': 'albums_info'})[0]
    album_and_artist = albums_info.findAll('td', {'valign': 'top'})
    album_title = album_and_artist[1].a.string  # 专辑名称
    artist_title = album_and_artist[3].a.string # 艺人
    return album_title, artist_title, album_and_artist

def get_artistinfo(content):
    artist_body = bs4.BeautifulSoup(content)
    location_genere = artist_body.findAll('td', {'valign': 'top'})
    location = location_genere[1].string    # 歌手国家
    if len(location_genere) >= 4 and location_genere[2].string == u'风格：':
        genere = location_genere[3].findAll('a')   # 歌手风格
        generes = map(lambda x: x.string, genere)
    else:
        generes = None

    return location, generes

class Application(tornado.web.Application):
    def __init__(self):
        handlers=[
            (r"/", HomeHandler),
            (r"/q", SearchHandler),
            (r"/sid/(\d+$)", SongHandler)
        ]
        settings = dict(
            title=u"Xiami Search",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True
        )
        tornado.web.Application.__init__(self, handlers, **settings)

class SearchHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def get(self):
        key = self.get_argument('key', None)
        PageNo = self.get_argument('page', 1)
        if key:
            url_current = page_url(key, PageNo)
            Page_Next = int(PageNo) + 1
            url_next = page_url(key, Page_Next)
            client = tornado.httpclient.AsyncHTTPClient()

            content_current, content_next = yield [client.fetch(url_current),
                                                   client.fetch(url_next)]

            if content_current.code == 200 and content_next.code == 200 and content_current.body != 'null':

                content = content_current.body.replace('&#039;', '\'')  # 替换乱码
                content = content.replace('&amp;', '&')
                raw_content = json.loads(content.decode())

                if int(PageNo) - 1 > 0:
                    Page_Previous = int(PageNo) -1
                else:
                    Page_Previous = None
                if content_next.body != 'null':
                    self.render('result.html', raw_content=raw_content, PageNo=PageNo, Page_Next=Page_Next, key=key, Page_Previous=Page_Previous)
                else:
                    self.render('result.html', raw_content=raw_content, PageNo=PageNo, Page_Next=None, key=key, Page_Previous=Page_Previous)
            else:
                self.write(u'未找到歌曲')

        else:
            self.write(u"没有参数")

class HomeHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('search.html')

class SongHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def get(self, sid):
        client = tornado.httpclient.AsyncHTTPClient()
        song_url = u'http://www.xiami.com/song/' + str(sid)
        response = yield client.fetch(song_url)
        if response.code == 200:
            album_title, artist_title, album_and_artist = get_songinfo(response.body)

            if album_and_artist[1].a['href'][0] != 'h' and album_and_artist[3].a['href'][0] != 'h':
                artist_url = u'http://www.xiami.com' + album_and_artist[3].a['href']
                artist_id = album_and_artist[3].a['href'][8::]
                print artist_id
                album_url = u'http://www.xiami.com' + album_and_artist[1].a['href']

                response_artist, response_album = yield map(lambda x: client.fetch(x), [artist_url, album_url])
                if response_artist.code == 200 and response_album.code == 200:
                    location, generes = get_artistinfo(response_artist.body)
                    album_rank, album_votes, lang, com, date = get_albuminfo(response_album.body)
                    song_info = dict(song_id = sid, location=location, generes=generes, album_title=album_title,
                                     artist_title=artist_title, album_rank=album_rank, artist_id=artist_id,
                                     album_votes=album_votes, lang=lang, com=com, date=date)
                    self.render('test.html', song_info=song_info)
                else:
                    # self.write('error: api调用错误')
                    pass

            elif album_and_artist[1].a['href'][0] != 'h' and album_and_artist[3].a['href'][0] == 'h':
                album_url = u'http://www.xiami.com' + album_and_artist[1].a['href']
                response_album = yield client.fetch(album_url)
                if response_album.code == 200:
                    album_rank, album_votes, lang, com, date = get_albuminfo(response_album.body)
                    song_info = dict(song_id = sid, location=None, generes=None, album_title=album_title,
                                     artist_title=artist_title, album_rank=album_rank, artist_id=None,
                                     album_votes=album_votes, lang=lang, com=com, date=date)
                    self.render('test.html', song_info=song_info)
                else:
                    # self.write('error: api调用错误')
                    pass

        else:
            # self.write('error: api调用错误')
            pass


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()

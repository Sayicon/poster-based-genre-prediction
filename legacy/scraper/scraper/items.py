import scrapy


class MovieItem(scrapy.Item):
    tmdb_id = scrapy.Field()
    title = scrapy.Field()
    genres = scrapy.Field()
    poster_url = scrapy.Field()

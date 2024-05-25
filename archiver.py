import requests, time, sys, bs4, os, json, datetime
from ebooklib import epub

USERNAME = os.environ.get("WATTPAD_USERNAME", "")
TOKEN = os.environ.get("TOKEN", "")
AGENT = os.environ.get("AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/105.0.0.0 Safari/537.36")

MULTITHREAD = os.environ.get("MULTITHREAD", "false").lower() == "true"
OUTPUT = os.environ.get("OUTPUT", "./output")

RATELIMIT = int(os.environ.get("RATELIMIT", "20"))
MAX_STORIES = int(os.environ.get("MAX_STORIES", "-1"))

ENDPOINT = "https://www.wattpad.com/api/v3/users/{username:s}/library"
FIELDS = "stories(id,title,createDate,modifyDate,voteCount,readCount,commentCount,description,url,firstPublishedPart," \
	+ "cover,language,isAdExempt,user(name,username,avatar,location,highlight_colour,backgroundUrl,numLists," \
	+ "numStoriesPublished,numFollowing,numFollowers,twitter),completed,isPaywalled,numParts,lastPublishedPart," \
	+ "parts(id,title,url,modifyDate,length,wordCount,videoId,photoUrl,commentCount,voteCount,readCount,voted,private," \
	+ "pages,text_url,rating,deleted,draft,isAdExempt,hasBannedHeader,dedication(name,url),source(url,label)),tags," \
	+ "categories,rating,rankings,tagRankings,language,copyright,sourceLink,firstPartId,deleted,draft,hasBannedCover,length)," \
	+ "total,nextUrl" # Subset of fields.txt

LANGUAGES = {
	1: "en",
	3: "it",
}

SYMBOLS = set(r"""`~!@#$%^&*()_-+={[}}|\:;"'<,>.?/""")

errors = 0

if MULTITHREAD:
	import threading

	class TimeEvent(threading.Event):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.clear()

		def set(self, *args, **kwargs):
			self.__time = time.time()
			super().set(*args, **kwargs)
		
		def clear(self, *args, **kwargs):
			self.__time = float("inf")
			super().clear(*args, **kwargs)

		def set_time(self):
			return self.__time

	err_event = TimeEvent()
	reqlock = threading.Lock()

# Max nanosecond delay between requests
req_delay = 1e+9 / RATELIMIT
last_request = time.time_ns()

def get_request(url, stream=None, **kwargs):
	def __req(wait=True):
		global last_request, req_delay
		
		if MULTITHREAD:
			with reqlock:
				if time.time_ns() - last_request < req_delay:
					time.sleep((req_delay - (time.time_ns() - last_request)) / 1e+9)
				
				last_request = time.time_ns()

		req = requests.get(url, params=kwargs, stream=stream,
				headers={'User-Agent': AGENT}, cookies={"token": TOKEN})

		if req.status_code == 429:
			if MULTITHREAD and err_event.is_set() and wait:
				err_event.wait()
			else:
				if MULTITHREAD:
					print(">>> Rate limit exceeded, halting everyone until reset")
					err_event.set()
				elif wait:
					print(">>> Rate limit exceeded, retrying every 2 seconds")

				time.sleep(2)
			return __req(wait=False)
		elif MULTITHREAD and time.time() > err_event.set_time():
			print(">>> Rate limit reset, resuming")
			err_event.clear()

		return req
	return __req()

def process_request(url, stream=None, **kwargs):
	request = get_request(url,  stream=stream, **kwargs)

	if request.status_code == 200:
		return request.json()
	else:
		message = None
		try:
			message = request.json()["message"]
		except:
			pass

		raise Exception("Request failed with code " + str(request.status_code) + (": " + message if message else ""))

def build_chapter_header(part):
	CHAPTER_HEADER = """
		<center>
			<h1 style="margin-bottom:13px;">{title:s}</h1>
			{dedication_html:s}
			<p style="margin-top:0px;margin-bottom:10px">Reads: {reads:d} | Votes: {votes:d} | Comments: {comments:d}</p>
			<br>
		</center>
	"""

	DEDICATION_HTML = '<p style="margin-top:0px;margin-bottom:13px;">Dedicated to: <a href="{url:s}">{name:s}</a></p>'
	dedication = DEDICATION_HTML.format(url=part["dedication"]["url"], name=part["dedication"]["name"]) \
		if len(part["dedication"]) > 0 else ""

	return CHAPTER_HEADER.format(title=part["title"], dedication_html=dedication,
			reads=part["readCount"], votes=part["voteCount"], comments=part["commentCount"])

print("Initializing Wattpad Library Scraper")
print()

print("Username :\t", USERNAME)
print("Token\t :\t", TOKEN[:9] + "*" * 10 + TOKEN[-9:])
print("Agent\t :\t", AGENT)
print("Endpoint :\t", ENDPOINT.format(username=USERNAME))
print()

print("Output\t\t:\t\"" + OUTPUT + "\"")
print(f"Limit\t\t:\t{MAX_STORIES} stories" if MAX_STORIES > 0 else "Download everything")
print("Multithreading\t:\t" + (f"ON - Max rate: {RATELIMIT}" if MULTITHREAD else "OFF"))
print()

scrape_time = time.time()
print("Beginning scrape on " + datetime.datetime.fromtimestamp(scrape_time).strftime("%Y-%m-%d %H:%M:%S"))
print()

print("Getting library count")
count = process_request(ENDPOINT.format(username=USERNAME), fields="total")["total"]
print("Found " + str(count) + " stories in library")
print()

print(f"Downloading library")
t = time.time()
result = process_request(ENDPOINT.format(username=USERNAME), fields=FIELDS, limit=count, offset=0)

print("Downloaded " + str(len(result["stories"])) + " story datasets, took " + str(round(time.time() - t, 2)) + "s")
print()

print("Processing stories into EPUB format")
all = time.time()

os.makedirs(OUTPUT, exist_ok=True)

cover_template = None
with open("templates/cover.xhtml") as f:
	cover_template = f.read()

title_template = None
with open("templates/title.xhtml") as f:
	title_template = f.read()

print("Loaded templates\n")

threads = []

i = 0
for story in result["stories"]:
	if MAX_STORIES >= 0 and i >= MAX_STORIES:
		print(f"Processed {i} stories, stopping because limit is set at {MAX_STORIES}\n")
		break
	i += 1
	
	def process_story(story):
		global errors

		loc = time.time()
		filename = os.path.join(OUTPUT, "".join(c for c in story["title"] if c not in SYMBOLS).replace(" ", "_") + ".epub")

		print("Processing " + story["title"] + " (" + str(story["id"]) + ")")

		book = epub.EpubBook()
		book.set_identifier("wp" + story["id"])
		book.set_title(story["title"])

		if story["language"]["id"] in LANGUAGES:
			book.set_language(LANGUAGES[story["language"]["id"]])
		else:
			print("Unknown language tag for ID " \
				+ f"{str(story['language']['id'])} (\"{story['language']['name']}\"), " \
				+ "defaulting to \"en\"", file=sys.stderr)
			book.set_language("en")

		book.add_author(f"{story['user']['name']} ({story['user']['username']})")
		book.set_cover("cover.jpg", get_request(story["cover"]).content)

		# Buttload of metadata ('cause we've got it so why not)
		book.add_metadata('DC', 'description', story["description"])
		book.add_metadata('DC', 'publisher', "Wattpad")
		book.add_metadata('DC', 'date', story["createDate"])
		book.add_metadata('DC', 'subject', ", ".join(story["tags"]))
		book.add_metadata('DC', 'type', "Text")
		book.add_metadata('DC', 'format', "application/epub+zip")
		book.add_metadata('DC', 'identifier', "wp" + story["id"])
		book.add_metadata('DC', 'source', story["url"])
		book.add_metadata('DC', 'language', book.language)
		book.add_metadata('DC', 'creator', story["user"]["name"])
		book.add_metadata('DC', 'creator', story["user"]["username"])

		book.add_metadata('OPF', 'reads', str(story["readCount"]), {'property':'dcterms:extent'})
		book.add_metadata('OPF', 'votes', str(story["voteCount"]), {'property':'dcterms:extent'})
		book.add_metadata('OPF', 'comments', str(story["commentCount"]), {'property':'dcterms:extent'})
		book.add_metadata('OPF', 'created', story["createDate"], {'property':'dcterms:extent'})
		book.add_metadata('OPF', 'updated', story["modifyDate"], {'property':'dcterms:extent'})
		book.add_metadata('OPF', 'scraped', str(scrape_time), {'property':'dcterms:extent'})

		cover = epub.EpubHtml(title="Cover", file_name="cover_page.xhtml", lang=book.language, 
			content=cover_template.format(title=story["title"]).encode())
		title = epub.EpubHtml(title="Title Page", file_name="title.xhtml", lang=book.language,
			content=title_template.format(
				title=story["title"], 
				author=story["user"]["name"], 
				username=story["user"]["username"],
				description=story["description"],
				reads=story["readCount"],
				votes=story["voteCount"],
				comments=story["commentCount"],
				first_publish=story["createDate"],
				last_update=story["modifyDate"]).encode())

		book.add_item(cover)
		book.add_item(title)

		toc = [cover, title]
		for part in story["parts"]:
			print("\tDownloading part \"" + part["title"] + "\"")

			chap = epub.EpubHtml(
					uid=str(part["id"]),
					title=part["title"], 
					file_name=str(part["id"]) + ".xhtml")

			orig = get_request(part["text_url"]["text"]).content

			try:
				err = json.loads(orig.decode())
				print(f"Error while downloading part \"{part['title']}\": {err['message']}", file=sys.stderr)
				errors += 1
			except:
				pass

			# Building header
			orig = build_chapter_header(part).encode() + orig

			if b"<img" in orig:
				soup = bs4.BeautifulSoup(orig, "html.parser")
				for img in soup.find_all("img"):
					url = img["src"]
					if "img.wattpad.com" in url:
						print(f"\t\tRelinking image \"{ (url[:51] + '...') if len(url) > 54 else url }\"")

						imgname = f"images/{part['id']}/{url.split('/')[-1]}"
						
						book.add_item(epub.EpubItem(
								file_name=imgname,
								media_type="image/jpeg",
								content=get_request(url).content))
						img["src"] = imgname
				chap.set_content(soup.prettify())
			else:
				chap.set_content(orig)

			toc.append(chap)
			book.add_item(chap)

		book.toc = tuple(toc)
		book.spine = ['nav', *toc]

		book.add_item(epub.EpubNav())
		book.add_item(epub.EpubNcx())

		epub.write_epub(filename, book)

		print(f"Saved {story['title']} by {story['user']['name']} to {filename}, took {round(time.time() - loc, 2)}s")
		print()

	if MULTITHREAD:
		t = threading.Thread(target=process_story, daemon=True, args=(story,))
		threads.append(t)
		t.start()
	else:
		process_story(story)

if MULTITHREAD:
	print("Waiting for all threads to finish")

	try:
		for t in threads:
			while t.is_alive():
				t.join(1)
	except KeyboardInterrupt:
		print("Interrupted, terminating all threads")
		sys.exit(1)
	print("\n\nAll jobs done\n")

print("Processed " + str(len(result["stories"])) + " stories with " + str(errors) + " errors, took " + str(round(time.time() - all, 2)) + "s")

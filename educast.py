import sys, glob, os, io
import traceback
import datefinder
import ffmpy
import eyed3
import json
import pytz
import pysftp
import textwrap
import internetarchive
import dateutil.parser
from PIL import ImageFont, Image, ImageDraw
from datetime import datetime as dt
from feedgen.feed import FeedGenerator

# debug handlers
_upload_to_internet_archive = True
_upload_to_domain = True
_move_source_files = True

# domain details
DomainPath = './files/podcasts/srvusd/'
DomainHost = 'ssh.phx.nearlyfreespeech.net'
DomainUser = 'sgoodrow_scottgoodrow'
DomainPass = 'M0ksh41sd34dNFS'

# podtrac details (podcast stats)
PodtracStub = 'http://dts.podtrac.com/redirect.mp3/'

# internet archive details (free host)
InternetArchiveDestination     = 'SRVUSD'
InternetArchiveDestinationStub = 'https://archive.org/details/' + InternetArchiveDestination
InternetArchiveDownloadStub    = 'https://archive.org/download/' + InternetArchiveDestination

# podcast details
SchoolDistrict       = 'San Ramon Valley Unified School District'
SchoolDistrictAbrv   = 'SRVUSD'
BoardOfEducation     = 'Board of Education'
BoardOfEducationAbrv = 'BOE'
Meeting              = 'Meeting'
LocalGovernment      = 'Local Government'
TimeZone             = 'US/Pacific'

# feed details
class Feed:
    Stub          = 'https://www.scottgoodrow.com/files/podcasts/srvusd/'
    URI           = 'https://www.scottgoodrow.com/'
    Title         = 'SRVUSD BOE Podcast'
    OwnerName     = "Scott Goodrow"
    OwnerEmail    = "podcast@scottgoodrow.com"
    Author        = {'name':OwnerName,'email':OwnerEmail}
    LinkAlternate = 'https://www.scottgoodrow.com/files/podcasts/srvusd/feed.rss'
    LinkSelf      = 'https://www.scottgoodrow.com/index.php/podcasts/srvusd/'
    Logo          = 'https://www.scottgoodrow.com/files/podcasts/srvusd/cover.jpeg'
    Subtitle      = 'Unofficial Podcast of San Ramon Valley Unified School District Board of Education Meetings'
    Language      = 'en'

    # itunes details
    class iTunes:
        Category = [{'cat':'Government & Organizations','sub':'Local'}]
        Complete = 'no'
        Explicit = 'no'
        Subtitle = 'Unofficial Podcast of SRVUSD BOE Meetings'
        Summary  = 'This is an unofficial podcast of the San Ramon Valley Unified School District Board of Education meetings, provided for easier access.'

def get_source_files(exts):
    files = []
    for ext in exts:
        ext = '.' + ext.lower()
        for file in os.listdir('.'):
            f, e = os.path.splitext(file)
            if e.lower() == ext:
                files.append(file)
    return files

def get_feed_json_files():
    return sorted(glob.glob('dst/*/*.json'), reverse=True)

def try_remove(file):
    if os.path.exists(file):
        os.remove(file)

def create_mp3(episode_info, src_file):
    # get files
    mp3_file = get_file(episode_info[EPISODE.NAME], 'mp3')

    # remove it if it exists already
    try_remove(mp3_file)

    # convert it
    print('Converting "' + src_file + '" to "' + mp3_file + '".')
    try:
        ffmpy.FFmpeg(global_options='-loglevel panic', inputs={src_file:None}, outputs={mp3_file:'-b:a 62K -vn'}).run()
        handle_success()
    except:
        handle_failure()

    return mp3_file, os.path.getsize(mp3_file)

def get_file(filename, ext):
    ext = '.' + ext
    for file in os.listdir('.'):
        f, e = os.path.splitext(file)
        if f.lower() == filename.lower() and e.lower() == ext.lower():
            return f + e

    return filename + ext

def handle_success():
    print('- Success!')

def handle_failure():
    print('- Failure!')
    traceback.print_exc()
    exit()

def replace_extension(file, ext):
    ext = '.' + ext
    f, e = os.path.splitext(file)
    return f + ext

def get_filename(file):
    f, e = os.path.splitext(file)
    return f

def get_episode_info(src_file):
    json_file = replace_extension(src_file, 'json')

    # initialize json if it does not exist
    if not os.path.exists(json_file):
        with open(json_file, 'w') as file:
            json.dump({EPISODE.CHAPTERS:[]}, file)

    print('Loading episode info from json file "' + json_file + '".')
    try:
        episode_info = json.load(open(json_file))
        handle_success()
    except:
        handle_failure()

    # assign additional info
    print('Getting additional episode info from "' + src_file + '".')
    filename = get_filename(src_file)
    matches = list(datefinder.find_dates(filename, source=True))
    if len(matches) > 0:
        date = matches[0][0]
        episode_info[EPISODE.DATE] = dt.isoformat(date)
        episode_info[EPISODE.YYMMDD] = date.strftime('%y%m%d')
        episode_info[EPISODE.MONTH_DAY_YEAR] = get_month_day_year('%B {S}, %Y', date)
        
        # Meeting
        descriptionType = filename.replace(matches[0][1], '')
        if descriptionType == '': descriptionType = Meeting
        descriptionType = descriptionType.replace('_', ' ').title().strip()
        
        # January 1st, 2017 - Meeting - San Ramon Valley Unified School District Board of Education.
        episode_info[EPISODE.DESCRIPTION] = ' '.join([episode_info[EPISODE.MONTH_DAY_YEAR], '-', descriptionType, '-', SchoolDistrict, BoardOfEducation + '.'])

        # SRVUSD BOE Meeting
        description_abrv = ' '.join([SchoolDistrictAbrv, BoardOfEducationAbrv, descriptionType])

        # 170124_srvusd_boe_meeting
        episode_info[EPISODE.NAME] = '_'.join([episode_info[EPISODE.YYMMDD], description_abrv.lower().replace(' ','_')])

        # 170124 SRVUSD BOE Meeting
        episode_info[EPISODE.TITLE] = ' '.join([episode_info[EPISODE.YYMMDD], description_abrv])

        # San Ramon Valley Unified School District
        episode_info[EPISODE.ARTIST] = SchoolDistrict
        
        # Board of Education 2017
        episode_info[EPISODE.ALBUM] =  BoardOfEducation

        # Year
        episode_info[EPISODE.YEAR] = str(date.year)

        handle_success()
    else:
        handle_failure()

    return json_file, episode_info

def tag_mp3(episode_info, mp3_file, jpeg_file):
    mp3 = eyed3.load(mp3_file)

    # remove chapters
    for i in range(0, 999):
        if mp3.tag.chapters.get(u'chp' + str(i) != None):
            mp3.tag.chapters.remove(u'chp' + str(i))

    # create fresh table of contents object
    mp3.tag.table_of_contents.remove('toc')
    toc = mp3.tag.table_of_contents.set('toc', toplevel=True, child_ids=[], description=u'Table of Contents')

    # add chapters
    chapter_text = []
    chapters = episode_info[EPISODE.CHAPTERS]
    title = episode_info[EPISODE.TITLE]
    for i in range(0, len(chapters)):
        chpi = 'chp' + str(i)
        chapter_text.append(' - '.join([chapters[i][EPISODE.CHAPTER.TIME], chapters[i][EPISODE.CHAPTER.ITEM], chapters[i][EPISODE.CHAPTER.TEXT]]))
        start = get_chapter_ms(chapters, i)
        final = get_chapter_ms(chapters, i + 1)
        mp3.tag.chapters.set(chpi, (start, final))
        mp3.tag.chapters.get(chpi).title = chapters[i][EPISODE.CHAPTER.ITEM] + ' - ' + chapters[i][EPISODE.CHAPTER.TEXT]
        image_file = chpi + '.jpeg'
        create_image(episode_info, i, image_file)
        mp3.tag.chapters.get(chpi).sub_frames['APIC'] = eyed3.id3.frames.ImageFrame(description=u'Image for a chapter', image_data=open(image_file, 'rb').read(), image_url=None, mime_type='image/jpeg', picture_type=0)
        os.remove(image_file)
        toc.child_ids.append(chpi)

    # set tags
    mp3.tag.title        = unicode(episode_info[EPISODE.TITLE])
    mp3.tag.artist       = unicode(episode_info[EPISODE.ARTIST])
    mp3.tag.album        = unicode(episode_info[EPISODE.ALBUM])
    mp3.tag.year         = unicode(episode_info[EPISODE.YEAR])
    mp3.tag.release_date = unicode(episode_info[EPISODE.DATE])

    # set cover
    image = open(jpeg_file, 'rb').read()
    mp3.tag.images.set(3, image, 'image/jpeg', unicode(episode_info[EPISODE.DESCRIPTION]))

    # adjust description to include the chapter text
    chapter_text.insert(0, episode_info[EPISODE.DESCRIPTION])
    description_with_chapters = '\n'.join(chapter_text)
    mp3.tag.comments.set(unicode(description_with_chapters))

    # save with tags
    mp3.tag.save(mp3_file, version = (2,3,0))

    return description_with_chapters, mp3.info.time_secs

def create_episode_jpeg(episode_info):
    jpeg_file = get_file(episode_info[EPISODE.NAME], 'jpeg')
    create_image(episode_info, -1, jpeg_file)
    return jpeg_file

def upload_to_internet_archive(episode_info, file, mediatype):
    metadata = dict(
        title       =episode_info[EPISODE.TITLE], 
        description =episode_info[EPISODE.DESCRIPTION], 
        date        =dt.isoformat(dt.utcnow()),
        language    ='eng',
        mediatype   =mediatype)

    if _upload_to_internet_archive:
        print('Uploading "' + file + '" to "' + InternetArchiveDestinationStub + '".')
        try:
            r = internetarchive.upload(InternetArchiveDestination, file, metadata=metadata)
            handle_success()
        except:
            handle_failure()
    else:
        print('Skipping uploads to "' + InternetArchiveDestinationStub + '".')

    return InternetArchiveDownloadStub

def move_files_into_dir(dir, file_dir, files):
    path = os.path.join(dir, get_filename(file_dir))

    if dir == 'src':
        if not _move_source_files:
            print('Skipping moving to "' + path + '".')
            return

    if not os.path.exists(path):
        os.mkdir(path)

    for file in files:
        dest = os.path.join(path, file)
        os.rename(file, dest)
        print('Moved "' + file + '" to "' + dest + '".')

def get_number_ordinal(d):
    return 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10, 'th')

def get_month_day_year(format, t):
    return t.strftime(format).replace('{S}', str(t.day) + get_number_ordinal(t.day))
    
def get_chapter_ms(chapters, i):
    if i >=len(chapters):
        return None
    else:    
        return int((dt.strptime(chapters[i][EPISODE.CHAPTER.TIME], '%H:%M:%S') - dt(1900, 1, 1)).total_seconds() * 100)
        
def create_image(episode_info, playing_chapter_index, image_file):
    text = episode_info[EPISODE.TITLE]
    chapters = episode_info[EPISODE.CHAPTERS]

    font_color_normal = (255, 255, 255)
    font_color_playing = (255, 255, 0)
    font_size = 40
    font_padding = 10
    column_separation = 200
    font = ImageFont.truetype('assets/arial.ttf', font_size)
    
    # create layer cover
    layer_cover = Image.open('assets/cover.jpeg').convert('RGBA')
    layer_cover_width  = layer_cover.width
    layer_cover_height = layer_cover.height
    layer_padding = int(layer_cover_width * 0.1)
    
    # create text layer
    xMin = yMin = yMax = layer_padding
    layer_text = Image.new('RGBA', layer_cover.size, (0, 0, 0, 0))
    drawer = ImageDraw.Draw(layer_text)

    # text title
    layer_text_width, layer_text_height = drawer.textsize(text, font=font)    
    xMax = layer_cover.width - layer_padding
    yMax = max(yMax, layer_padding + layer_text_height)
    font_color = font_color_playing if playing_chapter_index is -1 else font_color_normal
    drawer.text((layer_padding, layer_padding), text, font_color, font)
    title_separation = 20
    title_height = font_size + title_separation

    # draw page entries
    x = 0
    y = layer_padding + title_height
    for c in range(len(chapters)):

        # entry padding
        y += font_padding

        time = chapters[c][EPISODE.CHAPTER.TIME]
        item = chapters[c][EPISODE.CHAPTER.ITEM]
        text = chapters[c][EPISODE.CHAPTER.TEXT]
        font_color = font_color_playing if c is playing_chapter_index else font_color_normal

        # draw time
        x = layer_padding
        drawer.text((x, y), time, font_color, font)

        # draw item
        x += column_separation
        drawer.text((x, y), item, font_color, font)

        # draw text as word-wrapped lines
        x += column_separation
        lines = get_wrapped_lines(drawer, text, font, (layer_cover.width - layer_padding) - (x))
        if len(lines) == 0:
            y += font_size
        else:
            for line in lines:
                drawer.text((x, y), line, font_color, font)
                layer_text_width, layer_text_height = drawer.textsize(line, font)
                y += font_size
        
        # capture max y
        yMax = max(yMax, y)

        # only render the first page...
        if y > layer_cover.height - layer_padding:
            break

    # create text box layer
    layer_text_box = Image.new('RGBA', layer_cover.size, (0, 0, 0, 0))
    drawer = ImageDraw.Draw(layer_text_box)
    border = int(font_size * 0.5)
    xMin -= border
    yMin -= border
    xMax += border
    yMax += border
    opacity = 200
    drawer.rectangle([(xMin, yMin), (xMax, yMax)], fill=(0, 0, 0, opacity))
        
    # blend layers
    image = Image.alpha_composite(layer_cover, layer_text_box)
    image = Image.alpha_composite(image, layer_text)
    
    # save file
    image.save(image_file)

def get_wrapped_lines(drawer, text, font, wrap_size):
    words = text.split()  
    lines = [] # prepare a return argument
    lines.append(words) 
    finished = False
    line_number = 0
    while not finished:
        line = lines[line_number]
        next_line = []
        inner_finished = False
        while not inner_finished:
            if drawer.textsize(' '.join(line), font)[0] > wrap_size:
                # this is the heart of the algorithm: we pop words off the current
                # sentence until the width is ok, then in the next outer loop
                # we move on to the next sentence. 
                next_line.insert(0,line.pop(-1))
            else:
                inner_finished = True
        if len(next_line) > 0:
            lines.append(next_line)
            line_number = line_number + 1
        else:
            finished = True
    tmp = []
    for line in lines:
        tmp.append(' '.join(line))
    lines = tmp

    return lines

def create_feed_entry_json_file(episode_info, description_with_chapters, mp3_size, mp3_duration):
    feed_entry_json_file = episode_info[EPISODE.NAME] + '.json'

    try_remove(feed_entry_json_file)

    # initialize empty json
    with open(feed_entry_json_file, 'w') as file:
        json.dump({}, file)

    # read empty
    with open(feed_entry_json_file, 'r') as file:
        data = json.load(file)

    # default
    data[FEED_ENTRY.ID]              = episode_info[EPISODE.NAME]
    data[FEED_ENTRY.TITLE]           = episode_info[EPISODE.TITLE]
    data[FEED_ENTRY.DESCRIPTION]     = description_with_chapters
    data[FEED_ENTRY.ENCLOSURE_URL]   = PodtracStub + InternetArchiveDownloadStub + '/' + get_file(episode_info[EPISODE.NAME], 'mp3')
    data[FEED_ENTRY.ENCLOSURE_SIZE]  = str(mp3_size)
    data[FEED_ENTRY.CHAPTER_VTT_URL] = Feed.Stub + episode_info[EPISODE.NAME] + '/' + get_file(episode_info[EPISODE.NAME], 'vtt')
    data[FEED_ENTRY.PUBLISHED]       = episode_info[EPISODE.DATE]

    # itunes
    data[FEED_ENTRY.ITUNES.DURATION] = str(mp3_duration)
    data[FEED_ENTRY.IMAGE]           = InternetArchiveDownloadStub + '/' + get_file(episode_info[EPISODE.NAME], 'jpeg')
    data[FEED_ENTRY.ITUNES.SUBTITLE] = episode_info[EPISODE.DESCRIPTION]
    data[FEED_ENTRY.ITUNES.SUMMARY]  = description_with_chapters

    # write data
    with open(feed_entry_json_file, 'w') as file:
        json.dump(data, file)

    return feed_entry_json_file

def create_vtt(episode_info):
    vtt_file = episode_info[EPISODE.NAME] + '.vtt'

    try_remove(vtt_file)

    # write header
    file = open(vtt_file, 'w')
    file.write('WEBVTT\n')

    # write chapters
    chapters = episode_info[EPISODE.CHAPTERS]
    for i in range(0, len(chapters)):
        item = chapters[i][EPISODE.CHAPTER.ITEM]
        text = chapters[i][EPISODE.CHAPTER.TEXT]
        time = chapters[i][EPISODE.CHAPTER.TIME]
        final = '99:59:59' if i+1 >= len(chapters) else chapters[i+1][EPISODE.CHAPTER.TIME]

        file.write('\n')
        file.write(time + '.000 --> ' + final + '.000\n')
        file.write(item + ' - ' + text + '\n')

    file.close()

    return vtt_file

def create_feed_files():
    # initialize feed
    fg = FeedGenerator()

    # defaults
    fg.id(Feed.URI)
    fg.title(Feed.Title)
    fg.author(Feed.Author)
    fg.link(href=Feed.LinkAlternate, rel='alternate')
    fg.link(href=Feed.LinkSelf, rel='self')
    fg.logo(Feed.Logo)
    fg.image(Feed.Logo, Feed.Title, Feed.LinkAlternate)
    fg.language(Feed.Language)
    fg.description(Feed.Subtitle)
    fg.pubDate(dt.now(pytz.timezone(TimeZone)))    

    # itunes
    fg.load_extension('podcast')
    fg.podcast.itunes_category(Feed.iTunes.Category)
    fg.podcast.itunes_author(Feed.OwnerName)
    fg.podcast.itunes_complete(Feed.iTunes.Complete)
    fg.podcast.itunes_explicit(Feed.iTunes.Explicit)
    fg.podcast.itunes_image(Feed.Logo)
    fg.podcast.itunes_owner(Feed.OwnerName, Feed.OwnerEmail)
    fg.podcast.itunes_subtitle(Feed.iTunes.Subtitle)
    fg.podcast.itunes_summary(Feed.iTunes.Summary)

    # add entries
    for feed_json_file in get_feed_json_files():
        with open(feed_json_file, 'r') as file:
            data = json.load(file)

        # defaults
        fe = fg.add_entry()
        fe.id(data[FEED_ENTRY.ID])
        fe.title(data[FEED_ENTRY.TITLE])
        #fe.description(data[FEED_ENTRY.DESCRIPTION])
        fe.enclosure(data[FEED_ENTRY.ENCLOSURE_URL], data[FEED_ENTRY.ENCLOSURE_SIZE], 'audio/mpeg')
        fe.content(data[FEED_ENTRY.DESCRIPTION])

        date = dateutil.parser.parse(data[FEED_ENTRY.PUBLISHED])
        date = date.replace(tzinfo=pytz.timezone(TimeZone))
        fe.published(date)

        # itunes
        fe.podcast.itunes_duration(data[FEED_ENTRY.ITUNES.DURATION])
        fe.podcast.itunes_image(data[FEED_ENTRY.IMAGE])
        fe.podcast.itunes_is_closed_captioned('no')
        fe.podcast.itunes_subtitle(data[FEED_ENTRY.ITUNES.SUBTITLE])
        fe.podcast.itunes_summary(data[FEED_ENTRY.ITUNES.SUMMARY])

    # create feeds
    feed_rss_file  = get_file('feed', 'rss')
    feed_atom_file = get_file('feed', 'atom')
    fg.rss_file(feed_rss_file, pretty=True)
    fg.atom_file(feed_atom_file, pretty=True)

    return feed_rss_file, feed_atom_file

def create_playlist_json_file():
    playlist_json_file = 'playlist.json'

    try_remove(playlist_json_file)

    # initialize empty json
    with open(playlist_json_file, 'w') as file:
        json.dump({}, file)

    # read empty
    with open(playlist_json_file, 'r') as file:
        playlist_data = json.load(file)
        
    # add feed data to playlist data
    playlist = []
    for feed_json_file in get_feed_json_files():
        with open(feed_json_file, 'r') as file:
            feed_data = json.load(file)

        playlist.append(
            {
            'file'   :feed_data[FEED_ENTRY.ENCLOSURE_URL],
            'image'  :feed_data[FEED_ENTRY.IMAGE],
            'title'  :feed_data[FEED_ENTRY.TITLE],
            'mediaid':feed_data[FEED_ENTRY.ID],
            'tracks' :
            [
                {
                    'file':feed_data[FEED_ENTRY.CHAPTER_VTT_URL],
                    'kind':'chapters'
                },
                {
                    'file'   :feed_data[FEED_ENTRY.CHAPTER_VTT_URL],
                    'label'  :'English',
                    'kind'   :'captions',
                    'default':'true'
                }
                ]
            })

    # write data
    with open(playlist_json_file, 'w') as file:
        json.dump({'playlist':playlist}, file, indent=4)

    return playlist_json_file

def upload_to_episode_domain(info, files):
    path = DomainPath + info[EPISODE.NAME]
    if _upload_to_domain:
        try:
            print('Uploading to "' + path + '".')
            with pysftp.Connection(DomainHost, username=DomainUser, password=DomainPass) as sftp:
                for file in files:
                    if not sftp.exists(path):
                        sftp.mkdir(path, mode=775)

                    sftp.put(file, path + '/' + file)
            handle_success()
        except:
            handle_failure()
    else:
        print('Skipping uploads to "' + path + '".')

def upload_to_domain(files):
    if _upload_to_domain:
        try:
            print('Uploading to "' + DomainPath + '".')
            with pysftp.Connection(DomainHost, username=DomainUser, password=DomainPass) as sftp:
                for file in files:
                    sftp.put(file, DomainPath + file)
            handle_success()
        except:
            handle_failure()
    else:
        print('Skipping uploads to "' + DomainPath + '".')

class PLAYLIST:
    ITEMS = 'items'
    IMAGE = 'image'

class EPISODE:
    DATE           = 'date'
    YYMMDD         = 'yymmdd'
    MONTH_DAY_YEAR = 'mdy'
    ALBUM          = 'album'
    ARTIST         = 'artist'
    NAME           = 'name'
    DESCRIPTION    = 'description'
    TITLE          = 'title'
    YEAR           = 'year'
    CHAPTERS       = 'chapters'
        
    class CHAPTER:
        TIME = 'time'
        ITEM = 'item'
        TEXT = 'text'
    
class FEED_ENTRY:
    ID              = 'id'
    TITLE           = 'title'
    DESCRIPTION     = 'description'
    ENCLOSURE_URL   = 'enclosure_url'
    ENCLOSURE_SIZE  = 'enclosure_size'
    CHAPTER_VTT_URL = 'chapter_vtt_url'
    PUBLISHED       = 'published'
    IMAGE           = 'image'

    class ITUNES:
        DURATION = 'duration'
        SUBTITLE = 'subtitle'
        SUMMARY  = 'summary'
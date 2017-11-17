import educast

# check each wma
for src_file in educast.get_source_files(['wma', 'mp4']):
    # setup episode
    print('Found "' + src_file + '" to process.')

    # get json episode info
    episode_info_json_file, episode_info = educast.get_episode_info(src_file)

    # convert to mp3 with tags
    mp3_file, mp3_size = educast.create_mp3(episode_info, src_file)

    # episode image
    jpeg_file = educast.create_episode_jpeg(episode_info)

    # setup chapters
    description_with_chapters, mp3_duration = educast.tag_mp3(episode_info, mp3_file, jpeg_file)

    # create vtt file
    vtt_file = educast.create_vtt(episode_info)
        
    # upload to internet archive
    educast.upload_to_internet_archive(episode_info, mp3_file, 'audio')
    educast.upload_to_internet_archive(episode_info, jpeg_file, 'image')

    # upload to episode domain
    educast.upload_to_episode_domain(episode_info, [vtt_file])

    # create rss entry source file
    feed_entry_json_file = educast.create_feed_entry_json_file(episode_info, description_with_chapters, mp3_size, mp3_duration)

    # move src files
    educast.move_files_into_dir('src', src_file, [src_file, episode_info_json_file])

    # move dst files
    educast.move_files_into_dir('dst', mp3_file, [mp3_file, feed_entry_json_file, vtt_file, jpeg_file])

# rebuild the rss
feed_rss_file, feed_atom_file = educast.create_feed_files()

# create json feed
playlist_json_file = educast.create_playlist_json_file()

# upload
educast.upload_to_domain([feed_rss_file, feed_atom_file, playlist_json_file])

# move 
educast.move_files_into_dir('dst', '', [feed_rss_file, feed_atom_file, playlist_json_file])
Flickr-FS
=========

Flickr-fs is a fuse filesystem that allows you to upload your files to flickr
as encoded `.png`s. It's also really slow and liable to explode at any moment,
so don't seriously use it.

To try this, create a folder somewhere (I suggest
/[media|mnt]/[username]/flickrfs). Then copy sampleconfig.py to config.py and
update the values to match ones you get from flickr's create an app page. Then,
run `python2 runflickrfs.py <folder>`, where folder is the folder you created
earlier. If everything goes well, after a few seconds you should get the message
that it sucessfully mounted. You can then run a few simple operations like
`ls`/`cp` on the filesystem.

The FS is pretty slow and unoptimized, but not unusable.

    time /bin/ls /media/me/mntpoint
    test  test1
    /bin/ls /media/me/mntpoint  0.00s user 0.00s system 0% cpu 1.830 total

However, it has the tendency to stall out sometimes and crash with a 503. I'm
not sure if that's because I'm doing something wrong or because Flickr is
throttling me.

Requirements:
    python 2.7.3
    beautifulsoup4
    flickrapi
    fs
    PIL
    requests
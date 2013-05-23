from fs.expose import fuse
from flickrfs import FlickrFS, data_to_png, png_to_data
import requests
import sys


if __name__ == '__main__':
    if sys.argv[1] == 'encode':
        filefrom, fileto = sys.argv[2], sys.argv[3]
        with open(filefrom) as ff, open(fileto, 'w') as ft:
            img = data_to_png(ff.read())
            img.save(ft, 'png')
    elif sys.argv[1] == 'decode':
        filefrom, fileto = sys.argv[2], sys.argv[3]
        with open(filefrom) as ff, open(fileto, 'w') as ft:
            data = png_to_data(ff.read())
            ft.write(data)
    elif sys.argv[1] == 'upload':
        filefrom = sys.argv[2]
        with open(filefrom) as ff, tempfile.NamedTemporaryFile() as tf:
            img = data_to_png(ff.read())
            img.save(tf, 'png')
            print flickr.upload(filename=tf.name, format='bs4').photoid.text
    elif sys.argv[1] == 'download':
        imageid, fileto = sys.argv[2], sys.argv[3]
        with open(fileto, 'w') as ft:
            url = flickr.get_sizes(photo_id=imageid, format='bs4').sizes.find('size', label='Original')['source']
            ft.write(png_to_data(requests.get(url).content))
    elif len(sys.argv) == 2:
        mp = fuse.mount(FlickrFS(), sys.argv[1])
        print 'mounted your filckr account on', mp.path, 'pid', mp.pid, '.'
    else:
        print "Usage:"
        print "python runflickrfs.py <mntpoint> - mount your flickr account as a FUSE filesystem"
        print "python runflickrfs.py encode <from> <to> - encode the contents of a file as a png"
        print "python runflickrfs.py decode <from> <to> - decode the .png from into it's original contents"
        print "python runflickrfs.py upload <from> - upload the file to flickr and print the photo id"
        print "python runflickrfs.py download <photoid> - download a photo and decode it to it's original contents"

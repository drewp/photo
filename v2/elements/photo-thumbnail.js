Polymer({
    is: 'photo-thumbnail',
    properties: {
        img: { // RDF uri
            notify: true,
            observer: 'imgChanged'
        },
        uri: { // link to page
            notify: true,
        },
        size: { notify: true },
        imgSrc: { // image thumb
            notify: true,
        },
        noLink: {
            type: Boolean,
            notify: true
        }
    },
    imgChanged: function (img) {
        if (!img) {
            this.imgSrc = this.uri = null;
            return;
        }
        var uri = typeof img == 'string' ? img : img.uri;
        this.imgSrc = '';
        var size = this.size || 'small';
        this.imgSrc = uri.replace('http://', 'https://') + '?size=' + size;
        // video marker, uri link, click action
        // preload control, etc
        if (this.noLink) {
            this.uri = null;
        } else {
            this.uri = uri;
        }
    },
    computeHref: function (uri) {
        return uri + '/page';
    }
});

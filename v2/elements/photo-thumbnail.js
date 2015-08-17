Polymer({
    is: 'photo-thumbnail',
    properties: {
        img: {
            notify: true,
            observer: 'imgChanged'
        },
        size: { notify: true }
    },
    imgChanged: function (img) {
        if (!img) {
            this.imgSrc = this.uri = null;
            return;
        }
        this.uri = typeof img == 'string' ? img : img.uri;
        this.imgSrc = '';
        var size = this.size || 'small';
        this.async(function () {
            this.imgSrc = this.uri.replace('http://', 'https://') + '?size=' + size;
        }, null, 1);  // video marker, uri link, click action
        // preload control, etc
    },
    computeHref: function (uri) {
        return uri + '/page';
    }
});

Polymer("photo-thumbnail", {
    imgChanged: function() {
        var img = this.img;
        if (!img) {
            this.imgSrc = this.uri = null;
            return;
        }
        this.uri = (typeof img == 'string') ? img : img.uri;
        this.imgSrc = this.uri.replace('http://', 'https://') + '?size=small';
        // video marker, uri link, click action
        // preload control, etc
    }
});

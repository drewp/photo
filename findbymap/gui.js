var map = L.map('map').setView([37.72, -122.36], 10);
// shop at http://leaflet-extras.github.io/leaflet-providers/preview/

var Esri_NatGeoWorldMap = L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}', {
	attribution: 'Tiles &copy; Esri &mdash; National Geographic, Esri, DeLorme, NAVTEQ, UNEP-WCMC, USGS, NASA, ESA, METI, NRCAN, GEBCO, NOAA, iPC',
	maxZoom: 16
});
Esri_NatGeoWorldMap.addTo(map);
var Stamen_Terrain = L.tileLayer('https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg', {
	attribution: 'Map tiles by <a href="http://stamen.com">Stamen Design</a>, <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a> &mdash; Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>',
	subdomains: 'abcd',
	minZoom: 4,
	maxZoom: 18
});
//    Stamen_Terrain.addTo(map); // ok

function Marker(lat, long, uri) {
    var self = this;
    self.layer = L.marker([lat, long]);

    var popup = self.layer.bindPopup("<a href=\""+uri+"/page\"><img src=\""+uri+"?size=small\"></a>");

    self.layer.on('mouseover', popup.openPopup);

}

function ActiveMarkers(map) {
    var self = this;
    self.map = map;
    self.markers = {}; // pic or cluster uri : marker
    
    self.addPic = function (lat, long, uri) {
        if (self.markers[uri]) {
            return;
        }
        var m = new Marker(lat, long, uri);
        
        self.markers[uri] = m;
        m.layer.addTo(self.map);
    }

    self.displayedUris = function () {
        return _.keys(self.markers);
    }

    self.resetMarkersTo = function (newMarkers) {
        var newUris = _.pluck(newMarkers, 'uri');
        var showingUris = self.displayedUris();
        var toRemove = _.without(showingUris, newUris);
        toRemove.forEach(
            function (rm) {
                self.map.removeLayer(self.markers[rm].layer);
                delete self.markers[rm];
            });

        newMarkers.forEach(
            function (m) {
                self.addPic(m.lat, m.long, m.uri);
            });
        $("#status").text("now showing "+self.displayedUris().length+" markers");
    };

}
var activeMarkers = new ActiveMarkers(map);

function loadPhotos() {
    b = map.getBounds();
    $.ajax({
               type: "GET",
               url: "photos",
               data: {
                   w: b.getWest(),
                   e: b.getEast(),
                   n: b.getNorth(),
                   s: b.getSouth(),
                   zoom: map.getZoom(),
               },
               success: function (data) {
                   console.log("got", data);
                   activeMarkers.resetMarkersTo(data.markers);
               },
           });
}
loadPhotos();
map.on('viewreset', loadPhotos);
map.on('moveend', loadPhotos);

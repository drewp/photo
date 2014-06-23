assetManager = require('connect-assetmanager')
assetHandler = require('connect-assetmanager-handlers')

express = require('express')
http = require('http')
socketIo = require('socket.io')
app = express()
server = http.createServer(app)
server.listen(8031)
#app.engine("jade", build.jade)
#app.set('views', __dirname + "/..")

#app.use("/static", express.static(__dirname))
#app.use(express.logger())
#app.use(express.bodyParser())

prod = true
am = assetManager({
    'js' : {
        path: __dirname + "/",
        route: /\/bundle\.js/,
        dataType: 'javascript',
        files: [
            'static/page.js'
        ],
        stale: false,
        debug: true, #// minifier is breaking things.   !prod,
        xxpostManipulate: [
             (file, path, index, isLast, callback) ->
                    #// minifier bug lets '++new Date' from
                    #// socket.io.js into the result, which is a parse error.
                    callback(null, file.replace(/\+\+\(new Date\)/mig, 
                                            '\+\(\+(new Date))'))
            
        ]
        },
    'css' : {
        path: __dirname + "/",
        route: /\/bundle\.css/,
        dataType: 'css',
        stale: false,
        debug: !prod,
        files: [
                "static/style.css"]
                }
    });

    
app.get "/random", (req, res) ->
    res.header("content-type", "text/html") #application/xhtml+xml")
    res.render("random.jade", {"a":1})


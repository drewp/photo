class Model
  constructor: ->
    1
    
  getRandom: (n) =>
    o = ko.observable([])
    $.getJSON("randoms", {n: 3}, (result) =>
      o(result.randoms)
    )
    o

  getNewest: (n) =>
    o = ko.observable([])
    $.getJSON("set", {sort: "new", n: 3}, (result) =>
      o(result.newest)
    )
    o

    
app = Davis ->
  @get '/', (req) ->
    console.log("going to root")
  @get '/*any', (req) ->
    console.log("anything else")

# some clicks change the set and current; some change only the
# current; some change set but leave the current


app.start()
    
ko.applyBindings(new Model())

$(document).ready(function () {
  var colour;
  var gameSocket;
  var board;
  var game;

  function preStart(col, oppo) {
    colour = col;
    $("#play-btn").hide();
    $("#opponent-username").text(oppo);
    $("#opponent-username").show();
    $("#username").show();
  }

  function start() {
    game = new Chess();
    var whiteSquareGrey = "#a9a9a9";
    var blackSquareGrey = "#696969";

    function removeGreySquares() {
      $("#myBoard .square-55d63").css("background", "");
    }

    function greySquare(square) {
      var $square = $("#myBoard .square-" + square);

      var background = whiteSquareGrey;
      if ($square.hasClass("black-3c85d")) {
        background = blackSquareGrey;
      }

      $square.css("background", background);
    }

    function onDragStart(source, piece) {
      // do not pick up pieces if the game is over
      if (game.game_over()) return false;

      // or if it's not the player's side
      if (
        (colour === "white" && piece.search(/^b/) !== -1) ||
        (colour === "black" && piece.search(/^w/) !== -1)
      ) {
        return false;
      }

      // or if it's not that side's turn
      if (
        (game.turn() === "w" && piece.search(/^b/) !== -1) ||
        (game.turn() === "b" && piece.search(/^w/) !== -1)
      ) {
        return false;
      }
    }

    function onDrop(source, target) {
      removeGreySquares();

      // see if the move is legal
      var move = game.move({
        from: source,
        to: target,
        promotion: "q", // NOTE: always promote to a queen for example simplicity
      });

      // illegal move
      if (move === null) return "snapback";

      gameSocket.send(
        JSON.stringify({
          command: "move",
          san: move["san"],
        })
      );
    }

    function onMouseoverSquare(square, piece) {
      // exit if it's not the player's side
      if (piece) {
        if (
          (colour === "white" && piece.search(/^b/) !== -1) ||
          (colour === "black" && piece.search(/^w/) !== -1)
        ) {
          return false;
        }
      }

      // get list of possible moves for this square
      var moves = game.moves({
        square: square,
        verbose: true,
      });

      // exit if there are no moves available for this square
      if (moves.length === 0) return;

      // highlight the square they moused over
      greySquare(square);

      // highlight the possible squares for this piece
      for (var i = 0; i < moves.length; i++) {
        greySquare(moves[i].to);
      }
    }

    function onMouseoutSquare(square, piece) {
      removeGreySquares();
    }

    function onSnapEnd() {
      board.position(game.fen());
    }

    var config = {
      draggable: true,
      position: "start",
      onDragStart: onDragStart,
      onDrop: onDrop,
      onMouseoutSquare: onMouseoutSquare,
      onMouseoverSquare: onMouseoverSquare,
      onSnapEnd: onSnapEnd,
      orientation: colour,
    };
    board = Chessboard("myBoard", config);
    $(window).resize(board.resize);
  }

  function moved(san) {
    console.log("recieved:", san);
    game.move(san);
    board.position(game.fen());
  }

  $("#play-btn").click(function () {
    $(this).prop("disabled", true);
    $(this).html(
      `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
       Finding opponent...`
    );

    gameSocket = new WebSocket("ws://" + window.location.host + "/ws/game/");

    gameSocket.onmessage = function (e) {
      const data = JSON.parse(e.data);

      if (data["command"] === "start") {
        preStart(data["colour"], data["opponent"]);
        start();
      } else if (data["command"] === "abandoned") {
        alert(colour + " win by abandonment");
      } else if (data["command"] === "moved") {
        moved(data["san"]);
      }
    };

    gameSocket.onclose = function (e) {
      console.error("Chat socket closed unexpectedly");
    };
  });
});

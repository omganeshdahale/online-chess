$(document).ready(function () {
  var colour;
  var board;
  var game;
  var userDeadline;
  var opponentDeadline;
  var userIntervalID;
  var opponentIntervalID;
  var gameover = false;

  const DURATION = 10 * 60 * 1000; // in ms
  const DUR_SEC = Math.floor((DURATION / 1000) % 60);
  const DUR_MIN = Math.floor(DURATION / (1000 * 60));
  const DUR_SEC_TEXT = DUR_SEC < 10 ? `0${DUR_SEC}` : DUR_SEC;
  const DUR_MIN_TEXT = DUR_MIN < 10 ? `0${DUR_MIN}` : DUR_MIN;

  function preStart(col, user, oppo) {
    /*set var colour and gameover, hide play button, update opponent username, timers and show player containers.*/
    colour = col;
    gameover = false;
    $("#play-btn").hide();
    $("#opponent-username").text(oppo);
    $("#opponent-timer").text(`${DUR_MIN_TEXT}:${DUR_SEC_TEXT}`);
    $("#opponent-timer").removeClass("badge-warning badge-danger");
    $("#username").text(`You (${user})`);
    $("#user-timer").text(`${DUR_MIN_TEXT}:${DUR_SEC_TEXT}`);
    $("#user-timer").removeClass("badge-warning badge-danger");
    $("#opponent-container").show();
    $("#user-container").show();
  }

  function start() {
    /*Initialize and configure game and board.*/
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

      // gameover by abandonment or timeout
      if (gameover) return false;

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

      const isPromotion =
        game
          .moves({ verbose: true })
          .filter(
            (move) =>
              move.from === source &&
              move.to === target &&
              move.flags.includes("p")
          ).length > 0;

      if (isPromotion) {
        let promotion = prompt(
          "Enter\nq for queen\nn for knight\nr for rook\nb for bishop",
          "q"
        );
        if (!["q", "n", "r", "b"].find((element) => element === promotion))
          promotion = "q";

        var move = game.move({
          from: source,
          to: target,
          promotion: promotion,
        });
      } else {
        var move = game.move({
          from: source,
          to: target,
        });
      }

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
      if (gameover) return false;

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

  function moved(san, col, deadline) {
    /*Update game and board, and start/stop timers.*/
    if (col !== colour) {
      game.move(san);
      board.position(game.fen());
      userDeadline = new Date(deadline);
      clearInterval(opponentIntervalID);
      userIntervalID = setInterval(updateUserTimer, 100);
    } else {
      opponentDeadline = new Date(deadline);
      clearInterval(userIntervalID);
      opponentIntervalID = setInterval(updateOpponentTimer, 100);
    }
  }

  function endGame() {
    /*Set var gameover, enable and show play button, and clear timer intervals.*/
    gameover = true;
    $("#play-btn").prop("disabled", false);
    $("#play-btn").html("Play Again");
    $("#play-btn").show();
    clearInterval(userIntervalID);
    clearInterval(opponentIntervalID);
  }

  $("#play-btn").click(function () {
    $(this).prop("disabled", true);
    $(this).html(
      `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
       Finding opponent...`
    );

    gameSocket.send(JSON.stringify({ command: "find_opponent" }));
  });

  function updateTimer(t, selector) {
    const sec = Math.floor((t / 1000) % 60);
    const min = Math.floor((t / (1000 * 60)) % 60);

    const secText = sec < 10 ? `0${sec}` : sec;
    const minText = min < 10 ? `0${min}` : min;

    if (t <= 0)
      return gameSocket.send(JSON.stringify({ command: "end_if_timeout" }));
    else if (t <= (DURATION / 100) * 10) {
      $(selector).addClass("badge-danger");
      $(selector).removeClass("badge-warning");
    } else if (t <= (DURATION / 100) * 30)
      $(selector).addClass("badge-warning");

    $(selector).text(`${minText}:${secText}`);
  }

  function updateUserTimer() {
    const now = Date.now();
    const diff = userDeadline - now;
    updateTimer(diff, "#user-timer");
  }

  function updateOpponentTimer() {
    const now = Date.now();
    const diff = opponentDeadline - now;
    updateTimer(diff, "#opponent-timer");
  }

  const gameSocket = new WebSocket(
    "ws://" + window.location.host + "/ws/game/"
  );

  gameSocket.onmessage = function (e) {
    const data = JSON.parse(e.data);

    if (data.command === "start") {
      preStart(data.colour, data.client, data.opponent);
      start();
    } else if (data.command === "moved")
      moved(data.san, data.colour, data.deadline);
    else if (data.command === "win") {
      endGame();
      alert(data.winner_colour + " win by " + data.by);
    } else if (data.command === "draw") {
      endGame();
      alert("Draw");
    }
  };

  gameSocket.onclose = function (e) {
    console.error("Chat socket closed unexpectedly");
  };
});

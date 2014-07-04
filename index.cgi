#!/usr/bin/perl

use CGI qw/:standard/;
use CGI::Cookie;
use XML::Simple;
use Class::Struct;
use Digest::MD5 qw(md5_hex);
use Set::Object;

# limit POST size
$CGI::POST_MAX        = 1024 * 100; # max 100K posts
$CGI::DISABLE_UPLOADS = 1;          # no uploads

# declare the wordNode struct
struct wordNode => {
    iden       => '$',
    xloc       => '$',
    yloc       => '$',
    reveal     => '$',
    val        => '$',
    answer     => '$',
    adjacent   => '$',
    crossblock => '$',
};

# get the form and cookie data
my $cgi   = new CGI;

my $word        = $cgi->param('word');
my $state       = $cgi->param('state');
my $stateMerge  = $cgi->param('statemerge');
my $cookieState = cookie('state');
my $usedCookie  = 0;

# use the cookie if the state is not set
if(length($state) == 0){
    $state      = $cookieState;
    $usedCookie = 1;
}

# if cookie state is used, validate format then update the state to include newly added blocks
if($usedCookie){
    # read in the XML file, save word data
    my $xml        = new XML::Simple;
    my $data       = $xml->XMLin('emr3WOqvR0.xml');
    my $startState = $data->{startstate};

    # check that the state is formatted properly
    my ($tempState, $check) = split('&c-', $state);
    $state = $tempState;
    if(!(goodCheck($state, $check) && $state =~ /^(\d+)((&\d+-\d+(,\d+)*)+)$|^(\d+)$/)){
        $state = $startState;
    }
    else{
        # check all crossblocks in the state
        %newBlocks = ();
        while($state =~ /(&(\d+)-(\d+(,\d+)*))/g){
            my $currentBlock = $2;
            my @revealed     = split(',', $3);
            my %wordsHere    = %{$data->{block}->{$currentBlock}->{word}};     # only read in the words in the current block

            # read in the data file
            my @nodes        = ();
            while(my ($id, $word) = each(%wordsHere)){
                my $w = wordNode->new( iden       => $id,
                                       xloc       => $word->{xloc},
                                       yloc       => $word->{yloc},
                                       reveal     => $word->{reveal},
                                       val        => $word->{val},
                                       answer     => $word->{answer},
                                       adjacent   => $word->{adjacent},
                                       crossblock => $word->{crossblock},
                                     );

                @nodes[$id] = $w;
            }

            foreach $wordIdx (@revealed){
                $word = @nodes[$wordIdx];

                # skip if not a crossblock
                if(length($word->crossblock) == 0){
                    next;
                }

                my ($otherBlock, $otherWordIdx) = split(',', $word->crossblock);

                # skip if the other block is already in the state
                if(index($state, "&$otherBlock-") != -1){
                    next;
                }

                # add to the list of new blocks to be appended to the state
                if(!exists($newBlocks{$otherBlock})){
                    my @tempArray           = ();
                    $newBlocks{$otherBlock} = \@tempArray;
                }

                push(@{$newBlocks{$otherBlock}}, $otherWordIdx);
            }
        }

        # append the new blocks to the state
        while(my ($block, $arrRef) = each(%newBlocks)){
            my $newWords = arrayToComma($arrRef);
            $state      .= "&$block-$newWords";
        }

        $state = $state . '&c-' . makeCheck($state);
    }
}

# merge games if another one is provided
if(length($stateMerge) > 0){
    # check that the state is formatted properly, merge if so
    my ($tempStateMerge, $check) = split('&c-', $stateMerge);
    if(goodCheck($tempStateMerge, $check) && $tempStateMerge =~ /^(\d+)((&\d+-\d+(,\d+)*)+)$|^(\d+)$/){
        my ($tempState, $check) = split('&c-', $state);

        # get the relevant state info from the two state strings
        $tempState       =~ /^(\d+)((.+)*)/;
        my $currentBlock  = $1;
        my $restOfState1  = $2;

        $tempStateMerge  =~ /^(\d+)((.+)*)/;
        my $restOfState2 = $2;
        
        # merge the two state strings
        # build the set of all visible blocks in both games
        my $blockSet = Set::Object->new;
        while($restOfState1 =~ /&(\d+)-/g){
            $blockSet->insert($1);
        }

        while($restOfState2 =~ /&(\d+)-/g){
            $blockSet->insert($1);
        }

        $state = $currentBlock;

        # merge block-by-block
        foreach my $thisBlock ($blockSet->members){
            my @words1 = ();
            if($restOfState1 =~ /&$thisBlock-(\d+(,\d+)*)/){
                @words1 = split(',', $1);
            }

            my @words2 = ();
            if($restOfState2 =~ /&$thisBlock-(\d+(,\d+)*)/){
                @words2 = split(',', $1);
            }

            # build the intersection of the two word sets
            my $wordSet = Set::Object->new;
            $wordSet->insert(@words1);
            $wordSet->insert(@words2);

            # append to the state
            $state .= "&$thisBlock-";

            foreach my $word ($wordSet->members){
                $state .= "$word,";
            }

            chop($state);
        }

        # append the check string
        $state .= '&c-' . makeCheck($state);
    }
}

gameLogic($word, $state);

# gameLogic(inputWord, state)
# Advances the game based on the current state and user input
# state format: <currentBlock>&<block#>-<unlocked1>,<unlocked2>,...,<unlockedN>&<block#>-<unlocked1>,...,<unlockedN>&...&c-<check hash>
#           ex: 7&7-1,2,9,12&9-0,14,20&c-983ca8112f0
sub gameLogic{
    # check that the number of arguments is satisfied, save the paramters if so
    my $arraySize = @_;
    if($arraySize != 2){
        return '';
    }
    my ($inputWord, $state) = @_;

    my $inputState = $state;

    # read in the XML file, save word data
    my $xml        = new XML::Simple;
    my $data       = $xml->XMLin('emr3WOqvR0.xml');
    my $startState = $data->{startstate};
    my $metaAnswer = $data->{metagame};
    my $winScreen  = $data->{winscreen};

    # check that the state is formatted properly, reset to default state if not
    my ($tempState, $check) = split('&c-', $state);
    $state = $tempState;
    if(goodCheck($state, $check) && $state =~ /^(\d+)((&\d+-\d+(,\d+)*)+)$|^(\d+)$/){
        $state = $state;
    } else{
        $state = $startState; 
    }

    # parse the state
    $state           =~ /^(\d+)&/;
    my $currentBlock = $1;

    $state                =~ /&(($currentBlock)-(\d+(,\d+)*))/;
    my $currentBlockWhole = $1;
    my $currentWords      = $3;

    # read in the data file
    my @nodes        = ();
    my %wordsHere    = %{$data->{block}->{$currentBlock}->{word}};     # only read in the words in the current block
    my $categoryWord = 0;
    my $metaWord     = 0;
    while(my ($id, $word) = each(%wordsHere)){
        my $w = wordNode->new( iden       => $id,
                               xloc       => $word->{xloc},
                               yloc       => $word->{yloc},
                               reveal     => $word->{reveal},
                               val        => $word->{val},
                               answer     => $word->{answer},
                               adjacent   => $word->{adjacent},
                               crossblock => $word->{crossblock},
                             );

        @nodes[$id] = $w;

        # set the category word
        if($w->reveal == 2){
            $categoryWord = $w;
        }

        # set the meta game word
        if($w->reveal == 3){
            $metaWord = $w;
        }
    }

    my $blocksX = $data->{blocksx};
    my $blocksY = $data->{blocksy};

    # remove all non-alphabetic characters from the input word and set it to lower case
    $inputWord =~ s/[^(a-z|A-Z)]//g;
    $inputWord = lc($inputWord);

    my @revealedWords = split(',', $currentWords);       # read in the currently visible words from the state

    # check the input answer if provided
    if(length($inputWord) > 0 && length($inputWord) < 75){
        # show victory screen if meta answer is guessed
        if($inputWord eq $metaAnswer){
            print redirect( -URL => "$winScreen" );
        }


        %validAnswers = ();         # build a list of valid answers
        foreach $revealed (@revealedWords){
            # skip deleted nodes
            if(not defined(@nodes[$revealed])){
                next;
            }

            my $word = @nodes[$revealed];

            foreach $adj (split(',', $word->adjacent)){
                # skip if already revealed
                if(inArray(\@revealedWords, $adj) == 1){
                    next;
                }

                # otherwise, add to the list of valid answers
                my $adjWord = @nodes[$adj];

                foreach $answer (split(',', $adjWord->answer)){
                    $validAnswers{$answer} = $adj;
                }
            }
        }

        # check if the user-supplied word is in the list
        if(exists($validAnswers{$inputWord})){
            my $newRevealed   = $validAnswers{$inputWord};
            my $newBlockWhole = "$currentBlockWhole,$newRevealed";

            # update the state and list
            $state =~ s/$currentBlockWhole/$newBlockWhole/g;
            unshift(@revealedWords, $newRevealed);

            # check for border (cross-block) words
            my $word  = @nodes[$newRevealed];
            my $cross = $word->crossblock;

            # update state if this is a border word
            if(length($cross) > 1){
                my ($otherBlock, $otherWord) = split(',', $cross);

                # check if the other block is already unlocked
                $state =~ /&($otherBlock-\d+(,\d+)*)/;

                if(length($1) > 0){
                    my $otherState =  $1;
                    my $newState   =  "$otherState,$otherWord";
                    $state         =~ s/$otherState/$newState/g;
                }
                else{
                    $state .= "&$otherBlock-$otherWord";
                }
            }
        }
    }

    # set up the graphics - make nodes
    my $nodeString = '';
    my $linkString = '';

    my @visibleWords = @revealedWords;                  # build a list of visible words
    foreach $wordIdx (@revealedWords){
        # skip deleted nodes
        if(not defined(@nodes[$wordIdx])){
            next;
        }
        my $word     = @nodes[$wordIdx];                # make a revealed node

        if($word->reveal == 3) {
            $nodeString .= placeNode($word->val, $word->xloc, $word->yloc, 4);
        }
        else{
            $nodeString .= placeNode($word->val, $word->xloc, $word->yloc, 1);
        }

        my @adj  = split(',', $word->adjacent);         # get all adjacent nodes to the revealed one

        foreach $adjIdx (@adj){
            if(inArray(\@visibleWords, $adjIdx) == 0){  
                unshift(@visibleWords, $adjIdx);        # add to the list of visible nodes if it's not already there

                # reveal the category word if it's been reached
                if($categoryWord != 0 && $adjIdx == $categoryWord->iden){
                    push(@revealedWords, $adjIdx);
                    my $newBlockWhole = "$currentBlockWhole,$adjIdx";
                    $state =~ s/$currentBlockWhole/$newBlockWhole/g;
                }

                my $adjWord  = @nodes[$adjIdx];          # make an unrevealed node
                $nodeString .= placeNode($adjWord->val, $adjWord->xloc, $adjWord->yloc, $adjWord->reveal);
            }
        }
    }

    # make sure that category nodes are visible
    if($categoryWord != 0 && inArray(\@visibleWords, $categoryWord->iden) == 0){
        $nodeString .= placeNode($categoryWord->val, $categoryWord->xloc, $categoryWord->yloc, $categoryWord->reveal);
        unshift(@visibleWords, $categoryWord->iden);
    }
    if($metaWord != 0 && inArray(\@visibleWords, $metaWord->iden) == 0){
        $nodeString .= placeNode($metaWord->val, $metaWord->xloc, $metaWord->yloc, $metaWord->reveal);
        unshift(@visibleWords, $metaWord->iden);
    }

    # set up the graphics - link all visible nodes
    foreach $wordIdx (@visibleWords){
        # skip deleted nodes
        if(not defined(@nodes[$wordIdx])){
            next;
        }
        my $word = @nodes[$wordIdx];
        my @adj  = split(',', $word->adjacent);

        foreach $adjIdx (@adj){
            if($wordIdx < $adjIdx && inArray(\@visibleWords, $adjIdx) == 1){  # link if adjacent to a visible one
                my $adjWord  = @nodes[$adjIdx];
                $linkString .= placeLine($word->xloc, $word->yloc, $adjWord->xloc, $adjWord->yloc);
            }
        }
    }

    drawPage($nodeString, $linkString, $state, $blocksX, $blocksY, '');
}

# makeCheck(state)
# returns the check value for the given state
sub makeCheck{
    # define the salt
    my $SALT = '0118999881999119725...3';

    # save the parameters
    my $state = $_[0];

    return md5_hex("$state$SALT");
}

# goodCheck(state, check)
# returns true if the state and the check match
sub goodCheck{
    # make the salt
    my $SALT = '0118999881999119725...3';

    # save the parameters
    my ($state, $check) = @_;

    return md5_hex("$state$SALT") == $check;
}

# inArray(arrRef, integer)
# returns true if the integer is in the array
sub inArray{
    # save the parameters
    my @arr     = @{$_[0]};
    my $integer = $_[1];

    foreach $n (@arr){
        if($integer == $n){
            return 1;
        }
    }

    return 0;
}

# arrayToComma(arrRef)
# returns the elements in the given array, comma separated
sub arrayToComma{
    # save the params
    my @arr = @{$_[0]};

    my $str = '';
    foreach $elt (@arr){
        $str .= "$elt,";
    }

    chop($str);

    return $str;
}


# placeNode(word, xloc, yloc, reveal)
# Generates a string to be inserted in the output page that places a node.
# Reveal can take on the folling values
#   0 - regular node, hidden
#   1 - regular node, revealed
#   2 - category node, not yet reached
#   3 - hint node, hidden
#   4 - hint node, revealed
sub placeNode{
    # define the CSS classes for revealed and not revealed nodes
    $REVEALED     = 'revealed';
    $NOTREVEALED  = 'hidden';
    $CATEGORY     = 'category';
    $HINTHIDDEN   = 'hinthidden';
    $HINTREVEALED = 'hintrevealed';

    my $arraySize = @_;

    # check that the number of arguments is satisfied
    if($arraySize != 4){
        return '';
    }

    # save the parameters
    my ($word, $xloc, $yloc, $reveal) = @_;
    
    # translate the x and y locations so that the middle of cell is at that place
    $CELLHEIGHT = 21;
    $CELLWIDTH  = 10 + (5 * length($word));

    $yloc = $yloc - ($CELLHEIGHT / 2);
    $xloc = $xloc - ($CELLWIDTH  / 2);

    # build the output string
    if($reveal == 0){       # regular, hidden
        if($word =~ m/<br>/){
            $word =~ s/<br>/<&&>/g;
            $word =~ s/([a-z]|[A-Z])/./g;
            $word =~ s/<&&>/<br>/g;
        }
        else{
            $word         =~ s/([a-z]|[A-Z])/./g;
        }
        $outputString = "<div class = \"$NOTREVEALED\" style = \"top: $yloc"."px; left: $xloc"."px\">$word</div>";
    }
    elsif($reveal == 1){  # regular, revealed
        $outputString = "<div class = \"$REVEALED\" style = \"top: $yloc"."px; left: $xloc"."px\">$word</div>";
    }
    elsif($reveal == 2){  # category, unreached
        $outputString = "<div class = \"$CATEGORY\" style = \"top: $yloc"."px; left: $xloc"."px\">$word</div>";
    }
    elsif($reveal == 3){  # hint, hidden
        $word         =~ s/([a-z]|[A-Z])/./g;
        $outputString = "<div class = \"$HINTHIDDEN\" style = \"top: $yloc"."px; left: $xloc"."px\">$word</div>";
    }
    elsif($reveal == 4){  # hint, revealed
        $outputString = "<div class = \"$HINTREVEALED\" style = \"top: $yloc"."px; left: $xloc"."px\">$word</div>";
    }

    return $outputString;
}

# placeLine(x1, y1, x2, y2)
# Generates a string to be inserted in the output page that puts a line between two points.
sub placeLine{
    # define the graphics object to be invoked
    $GRAPHICSOBJ = 'jg';

    my $arraySize = @_;

    # check that the number of arguments is satisfied
    if($arraySize != 4){
        return '';
    }
    
    # save the parameters
    my ($x1, $y1, $x2, $y2) = @_;

    # build the output string
    $outputString = "$GRAPHICSOBJ.drawLine($x1, $y1, $x2, $y2);";
    
    return $outputString;
}

# drawPage(nodes, lines, state, blocksX, blocksX, debug)
# Draws the page and board with the specififed nodes, lines, and state
sub drawPage{

    my $arraySize = @_;

    # check that the number of arguments is satisfied
    if($arraySize != 6){
        return;
    }

    # save the parameters
    my ($nodes, $lines, $state, $blocksX, $blocksY, $debug) = @_;
    my $check = makeCheck($state);

    # build the minimap
    $state =~ /^(\d+)&(.+)*/;
    my $activeBlock = $1;
    my $restOfState = $2;

    my $tableStr = '<table class = "minimap">';
    foreach $i (0 .. ($blocksX - 1)){                   # each row
        $tableStr .= '<tr>';
        foreach $j (0 .. ($blocksY - 1)){               # each column
            my $blockID = ($i * $blocksX) + $j;

            # check if this is the current active block
            if($blockID == $activeBlock){
                $tableStr .= "<td class = \"current\"><img src = \"$blockID.png\"></td>";
                next;
            }

            # check if the block is revealed
            if(index($state, "&$blockID-") != -1){     # is revealed
                my $tempState = "$blockID&$restOfState";
                my $check     = makeCheck($tempState);
                $tableStr .= "<td class = \"other\"><form method = \"POST\" action = \"index.cgi\"><input type = \"hidden\" name = \"state\" value = \"$tempState&c-$check\"><input type = \"image\" src = \"$blockID.png\"></form></td>";
            }
            else{                   # is not revealed
                $tableStr .= "<td class = \"other\"> </td>";
            }
        }
        $tableStr .= '</tr>';
    }
    $tableStr .= '</table>';

    # write the state to a cookie
    my $cookie = cookie(-name => 'state', -value => "$state&c-$check", -expires => '+10y');
    print header(-cookie => $cookie);

    my $PAGETEMPLATE = <<"    EOT";
        <html>
            <head>
                <title>Krazy Kitchen</title>
                <script type = "text/javascript" src = "wz_jsgraphics.js"></script>
                <link rel = "stylesheet" type = "text/css" href = "layout.css" />
                <link rel = "image_src" href = "http://www.thesnooze.net/krazy/fbpreview.png" />
                <link rel = "shortcut icon" href = "favicon.ico">
            </head>

            <body onLoad='document.userinput.word.focus()'>
                <noscript>
                    Javascript is required for this game. Please enable it in your browser.
                </noscript>

                <script type="text/javascript"><!--
                    var jg = new jsGraphics();
                //--></script>


                <div id = "page-container">
                    <div id = "left-pane">
                        <div id = "padded">
                            <center>MINIMAP</center>
                            <center>$tableStr</center>
                            <br>
                            <p>
                            Welcome to the Krazy Kitchen word association puzzle. 
                            Use the box below to enter your guesses. See <a href = "http://thesnooze.net/blog/">my blog</a>
                            for the latest instructions, hints, updates, and bug reports. Leave a comment letting me know what you think of the game! Credit to ShyGypsy.com for the original Funny Farm game.
                            </p>
                            <br>
                            <form name = "userinput" method = "POST" action = "index.cgi">
                                <input type = "hidden" name = "state" value = "$state&c-$check">
                                <input type = "text" name = "word" maxlength = "100">
                            </form> (press enter)
                        </div>
                    </div>

                    <div id = "right-pane">
                        <div id = "board">
                            <script type="text/javascript"><!--
                                jg.setColor('#000000');
                                $lines
                                jg.paint();
                            //--></script>

                            $nodes
                        </div>
                    </div>

                    <div id = "bottom-pane">
                        <form name = "mergeinput" method = "POST" action = "index.cgi">
                        Current game: <input type = "text" style = "background-color: #9C9C9C;" name = "state" value = "$state&c-$check" readonly = "readonly" size = "100" onclick = "javascript:this.focus();this.select();"><br>
                        Merge game:  <input type = "text" name = "statemerge" size = "100"><input type = "submit" value = "Merge">
                        </form>
                    </div>
                </div>
            </body>
        </html>

    EOT

    print $PAGETEMPLATE;
    print $debug;
}

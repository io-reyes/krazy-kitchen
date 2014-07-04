#!/usr/bin/perl
use Set::Object;

my $state      = '12&12-22&c-455462d9dc0496f7700a1ebef0e9edf1';
my $stateMerge = '12&12-22,17,0&7-38,19,33,26,17&6-21&c-067bcaa9db69682778cf243ed6c68926';

print "Content-type: text/html\n\n";

if(length($stateMerge) > 0){
    # check that the state is formatted properly, merge if so
    my ($tempStateMerge, $check) = split('&c-', $stateMerge);
    if($tempStateMerge =~ /^(\d+)((&\d+-\d+(,\d+)*)+)$|^(\d+)$/){
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

        print "State 1: $restOfState1<br>State 2: $restOfState2<br>--<br>";

        # merge block-by-block
        foreach my $thisBlock ($blockSet->members){
            print "Block $thisBlock<br>";

            my @words1 = ();
            if($restOfState1 =~ /&$thisBlock-(\d+(,\d+)*)/){
                print "$1<br>";
                @words1 = split(',', $1);
            }

            my $words2 = ();
            if($restOfState2 =~ /&$thisBlock-(\d+(,\d+)*)/){
                print "$1<br>--<br>";
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
    }
}

print "$state\n";

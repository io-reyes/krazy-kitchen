use XML::Simple;
use Class::Struct;

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

# read in the XML file, save word data
my $xml          = new XML::Simple;
my $data         = $xml->XMLin('emr3WOqvR0.xml');
my $currentBlock = $ARGV[0];


my @nodes        = ();
my %wordsHere    = %{$data->{block}->{$currentBlock}->{word}};     # only read in the words in the current block

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

foreach $word1 (@nodes){
    my $id1 = $word1->iden;

    foreach $id2 (split(',', $word1->adjacent)){
	$word2 = @nodes[$id2];

	@word2adj = split(',', $word2->adjacent);
	if(inArray(\@word2adj, $id1) == 0){
            my $val1 = $word1->val;
            my $val2 = $word2->val;

            print "$val1 (#$id1) connects to $val2 (#$id2) but not vice versa\n";
	}
    }
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

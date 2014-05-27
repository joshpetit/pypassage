# -*- coding: utf-8 -*-
import bibledata
from collections import defaultdict

## Long term ##
#Implement string parsing



class Passage(object):
    def __init__(self, book, start_chapter=None, start_verse=None, end_chapter=None, end_verse=None, end_book=None, translation="ESV"):
        """
        Intialise and check passage reference. Missing information is filled in where it can be
        safely assumed. Infeasible passages will raise InvalidPassageException.
        
        'book' may be a name (e.g. "Genesis"), a standard abbreviation (e.g. "Gen") or an
        integer (i.e. Genesis = 1, Revelation = 66).
        """
        self.bd = bd = bible_data(translation)

        #Check book start
        if isinstance(book, int) or isinstance(book, long):
            #Book has been provided as an integer (1-66)
            self.start_book_n = int(book)
            if self.start_book_n > 66 or self.start_book_n < 1:
                raise InvalidPassageException()
        else:
            #Assume book has been provided as a string
            self.start_book_n = bd.book_numbers.get(str(book).upper(),None)
            if self.start_book_n == None:
                raise InvalidPassageException()

        #Check book end
        if end_book == None:
            self.end_book_n = self.start_book_n
        else:
            if isinstance(end_book, int) or isinstance(end_book, long):
                #Book has been provided as an integer (1-66)
                self.end_book_n = int(end_book)
                if self.end_book_n > 66 or self.end_book_n < 1:
                    raise InvalidPassageException()
            else:
                #Assume end_book has been provided as a string
                self.end_book_n = bd.book_numbers.get(str(end_book).upper(),None)
                if self.end_book_n == None:
                    raise InvalidPassageException()

        #Check and normalise numeric reference inputs
        (self.start_chapter, self.start_verse, self.end_chapter, self.end_verse) = check_reference(self.start_book_n, bd, start_chapter, start_verse, end_chapter, end_verse)

        #Raise exception now if passage is still invalid
        if not self.is_valid():
            raise InvalidPassageException()

        #Finish by setting self.start and self.end integers
        return self.setint()

    """ Old variable name for start_book_n was book_n """
    def get_book_n(self):
        return self.start_book_n
    def set_book_n(self, book_n):
        self.start_book_n = book_n
    book_n = property(get_book_n, set_book_n)

    def setint(self):
        """
        Set integers self.start and self.end, in order to represent passage starting and endings in purely
        numeric form. Primarily useful for efficient database filtering of passages.
        First two numerals are book number (eg. Gen = 01 and Rev = 66). Next three numerals are chapter, and
        final three numerals are verse. Thus Gen 3:5 is encoded as 001003005.
        """
        self.start = (self.start_book_n * 10**6) + (self.start_chapter * 10**3) + self.start_verse
        self.end   = (self.end_book_n * 10**6) + (self.end_chapter * 10**3)   + self.end_verse
        return
    
    def is_valid(self):
        """
        Return boolean denoting whether this Passage object is a valid reference or not. Note that while object
        always ensures passage is valid when it is instantiated, it may have been made invalid at a later time.
        """
        #Does book exist?
        if isinstance(self.start_book_n, int):
            if self.start_book_n > 66 or self.start_book_n < 1:
                return False
        else: return False
        #Are start_chapter, start_verse, end_chapter, and end_verse all integers?
        if not isinstance(self.start_chapter,int) or not isinstance(self.start_verse,int) or not isinstance(self.end_chapter,int) or not isinstance(self.end_verse,int): return False
        #Is end after start?
        if self.start_chapter > self.end_chapter:
            return False
        elif self.start_chapter == self.end_chapter:
            if self.end_verse < self.start_verse: return False
        #Do end chapter/verse and start verse exist?
        if self.bd.number_chapters[self.start_book_n] < self.end_chapter: return False
        if self.bd.last_verses[self.start_book_n, self.end_chapter] < self.end_verse: return False
        if self.bd.last_verses[self.start_book_n, self.start_chapter] < self.start_verse: return False
        #Are either start or end verses missing verses?
        if self.start_verse in self.bd.missing_verses.get((self.start_book_n, self.start_chapter),[]): return False
        if self.end_verse in self.bd.missing_verses.get((self.start_book_n, self.end_chapter),[]): return False
        #Everything checked; return True
        return True
    
    def number_verses(self):
        """ Return number of verses in this passage. """
        if not self.is_valid(): return 0
        if self.start_chapter == self.end_chapter:
            n = self.end_verse - self.start_verse + 1
            missing = self.bd.missing_verses.get((self.start_book_n,self.start_chapter),[])
            for verse in missing:
                if verse >= self.start_verse and verse <= self.end_verse: n -= 1
            return n
        else:
            n = self.end_verse + (self.bd.last_verses[self.start_book_n,self.start_chapter] - self.start_verse + 1)
            for chapter in range(self.start_chapter+1,self.end_chapter):
                n += self.bd.last_verses[self.start_book_n,chapter] - len(self.bd.missing_verses.get((self.start_book_n,chapter),[]))
            missing_start = self.bd.missing_verses.get((self.start_book_n,self.start_chapter),[])
            for verse in missing_start:
                if verse >= self.start_verse: n -= 1
            missing_end = self.bd.missing_verses.get((self.start_book_n,self.end_chapter),[])
            for verse in missing_end:
                if verse <= self.end_verse: n -= 1
            return n
        
    def proportion_of_book(self):
        """ Return proportion of current book represented by this passage. """
        return len(self)/float(self.book_total_verses())

    def complete_book(self):
        """ Return True if this reference is for a whole book. """
        return (self.start_chapter == self.start_verse == 1 and
                self.end_chapter == self.bd.number_chapters[self.start_book_n] and
                self.end_verse   == self.bd.last_verses[self.start_book_n, self.end_chapter])
    
    def complete_chapter(self, multiple=False):
        """
        Return True if this reference is for a (single) whole chapter.
        Alternatively, if multiple=True, this returns true if reference is for any number of whole chapters.
        """
        return (self.start_verse == 1 and
                (multiple == True or self.start_chapter == self.end_chapter) and
                self.end_verse == self.bd.last_verses[self.start_book_n, self.end_chapter])

    def truncate(self, number_verses=None, proportion_of_book=None):
        """
        Return truncated version of passage if longer than given restraints, or else return self.

        Arguments:
        number_verses -- Maximum number of verses that passage may be
        proportion_of_book -- Maximum proportion of book that passage may be

        For example:
        >>> Passage('Gen').truncate(number_verses=150)
        Passage(book=1, start_chapter=1, start_verse=1, end_chapter=6, end_verse=12)

        """
        #Check current length and length of limits
        current_length = len(self)
        limit = current_length
        if number_verses != None:
            if number_verses < limit: limit = number_verses
        if proportion_of_book != None:
            verses = int(proportion_of_book * self.book_total_verses())
            if verses < limit: limit = verses
        if current_length <= limit:
            #No need to shorten; return as-is.
            return self
        else:
            #Check that we're non-negative
            if limit < 1: return None
            #We need to shorten this passage. Iterate through passages until we've reached our quota of verses.
            n = 0
            for chapter in range(self.start_chapter, self.end_chapter+1):
                if chapter == self.start_chapter:
                    start_verse = self.start_verse
                else:
                    start_verse = 1
                if chapter == self.end_chapter:
                    end_verse = self.end_verse
                else:
                    end_verse = self.bd.last_verses[self.start_book_n, chapter]
                valid_verses = [v for v in range(start_verse, end_verse+1) if v not in self.bd.missing_verses.get((self.start_book_n, chapter),[]) ]
                if n + len(valid_verses) >= limit:
                    return Passage(self.start_book_n, self.start_chapter, self.start_verse, chapter, valid_verses[limit-n-1])
                else:
                    n += len(valid_verses)
            #If we've got through the loop and haven't returned a Passage object, something's gone amiss.
            raise Exception("Got to end_verse and still hadn't reached current_length!")
        
    def extend(self, number_verses=None, proportion_of_book=None):
        """
        Return extended version of passage if shorter than given restraints, or else return self.
        Same arguments as used by self.truncate
        
        For example, returning the first 50% of the verses in Genesis:
        >>> Passage('Gen',1,1).extend(proportion_of_book=0.5)
        Passage(book=1, start_chapter=1, start_verse=1, end_chapter=27, end_verse=38)
        
        """
        #First check if starting reference is valid:
        if (self.start_book_n > 66 or self.start_book_n < 1) or (self.start_chapter < 1 or self.start_chapter > self.bd.number_chapters[self.start_book_n]) or (self.start_verse < 1 or self.start_verse > self.bd.last_verses[self.start_book_n, self.start_chapter]): return None
        #Check current length and length of limits
        current_length = len(self)
        limit = current_length
        if number_verses != None:
            if number_verses > limit: limit = number_verses
        if proportion_of_book != None:
            verses = int(proportion_of_book * self.book_total_verses())
            if verses > limit: limit = verses
        if current_length >= limit:
            #No need to extend; return as-is.
            return self
        else:
            #We need to extend this passage. Do this by truncating the longest passage possible.
            end_chapter = self.bd.number_chapters[self.start_book_n]
            end_verse = self.bd.last_verses[self.start_book_n, end_chapter]
            return Passage(self.start_book_n, self.start_chapter, self.start_verse, end_chapter, end_verse).truncate(number_verses=limit)
        
    def book_total_verses(self):
        """ Return total number of verses in current book. """
        verses = 0
        for chapter in range(1,self.bd.number_chapters[self.start_book_n]+1):
            verses += self.bd.last_verses[self.start_book_n,chapter] - len(self.bd.missing_verses.get((self.start_book_n,chapter),[]))
        return verses
    
    def book_name(self, abbreviated = False):
        """ Return full or abbreviated book name. """
        if abbreviated:
            return self.bd.book_names[self.start_book_n][2]
        else:
            if self.start_book_n == 19 and self.start_chapter == self.end_chapter:
                return "Psalm"
            else:
                return self.bd.book_names[self.start_book_n][1]
            
    def reference_string(self, abbreviated = False, dash = "-"):
        """ Return string representation of Passage object. """
        if not self.is_valid(): return 'Invalid passage'
        if self.bd.number_chapters[self.start_book_n] == 1:
            if self.start_verse == self.end_verse:
                return self.book_name(abbreviated) + " " + str(self.start_verse)
            elif self.start_verse == 1 and self.end_verse == self.bd.last_verses[self.start_book_n, 1]:
                return self.book_name(abbreviated)
            else:
                return self.book_name(abbreviated) + " " + str(self.start_verse) + dash + str(self.end_verse)
        else:
            if self.start_chapter == self.end_chapter:
                if self.start_verse == self.end_verse:
                    return self.book_name(abbreviated) + " " + str(self.start_chapter) + ":" + str(self.start_verse)
                elif self.start_verse == 1 and self.end_verse == self.bd.last_verses[self.start_book_n, self.start_chapter]:
                    return self.book_name(abbreviated) + " " + str(self.start_chapter)
                else:
                    return self.book_name(abbreviated) + " " + str(self.start_chapter) + ":" + str(self.start_verse) + dash + str(self.end_verse)
            else:
                if self.start_verse == 1 and self.end_verse == self.bd.last_verses[self.start_book_n, self.end_chapter]:
                    if self.start_chapter == 1 and self.end_chapter == self.bd.number_chapters[self.start_book_n]:
                        return self.book_name(abbreviated)
                    else:
                        return self.book_name(abbreviated) + " " + str(self.start_chapter) + dash + str(self.end_chapter)
                else:
                    return self.book_name(abbreviated) + " " + str(self.start_chapter) + ":" + str(self.start_verse) + dash + str(self.end_chapter) + ":" + str(self.end_verse)
    
    def osisRef(self):
        """
        Return reference using the formal OSIS cannonical reference system.
        See http://www.bibletechnologies.net/ for details
        """
        return bibledata.osis.normative_book_names[self.start_book_n] + "." + str(self.start_chapter) + "." + str(self.start_verse) + "-" +\
               bibledata.osis.normative_book_names[self.start_book_n] + "." + str(self.end_chapter) + "." + str(self.end_verse)
    
    def __str__(self):
        """
        x.__str__() <==> str(x)
        Return passage string.
        """
        return self.reference_string()
    
    def __unicode__(self):
        """
        x.__unicode__() <==> unicode(x)
        Return unicode version of passage string, using en-dash for ranges.
        """
        return unicode(self.reference_string(dash=u"–"))
    
    def abbr(self):
        """ Return abbreviated passage string """
        return self.reference_string(abbreviated=True)
    
    def uabbr(self):
        """ Return unicode-type abbreviated passage string, using en-dash for ranges. """
        return unicode(self.reference_string(abbreviated=True, dash=u"–"))
    
    def __len__(self):
        """
        x.__len__() <==> len(x)
        Return number of verses in passage.
        """
        return int(self.number_verses())
    
    def __repr__(self):
        """
        x.__repr__() <==> x
        """
        return "Passage(book="+repr(self.start_book_n)+", start_chapter="+repr(self.start_chapter)+", start_verse="+repr(self.start_verse)+", end_chapter="+repr(self.end_chapter)+", end_verse="+repr(self.end_verse)+")"
    
    def __cmp__(self, other):
        """ Object sorting function. Sorting is based on start chapter/verse. """
        return cmp(self.start, other.start)
    
    def __eq__(self,other):
        """
        x.__eq__(y) <==> x == y
        Equality checking.
        """
        if not isinstance(other, Passage): return False
        if (self.start_book_n == other.start_book_n) and (self.start_chapter == other.start_chapter) and (self.start_verse == other.start_verse) and (self.end_chapter == other.end_chapter) and (self.end_verse == other.end_verse):
            return True
        else:
            return False
        
    def __ne__(self,other):
        """
        x.__ne__(y) <==> x != y
        Inequality checking.
        """
        return not self.__eq__(other)
    
    def __add__(self,other):
        """
        x.__add__(y) <==> x + y
        Addition. PassageCollection object returned.
        """
        if isinstance(other,Passage):
            return PassageCollection(self,other)
        elif isinstance(other,PassageCollection):
            return PassageCollection(self,other)
        else:
            return NotImplemented


class PassageCollection(list):
    """
    Class to contain list of Passage objects and derive corresponding reference strings
    """
    def __init__(self, *args):
        """
        PassageCollection initialisation. Passages to be in collection may be passed in directly or as lists.
        For example, the following is valid:
        PassageCollection( Passage('Gen'), Passage('Exo'), [Passage('Mat'), Passage('Mar')])
        """
        passages = []
        for arg in args:
            if isinstance(arg, Passage):
                passages.append(arg)
            elif isinstance(arg, list):
                for item in arg:
                    if isinstance(item, Passage): passages.append(item)
        super(PassageCollection, self).__init__(passages)
                    
    def reference_string(self, abbreviated=False, dash="-"):
        """
        x.reference_string() <==> str(x)
        Return string representation of these references.
        """
        #First checking easy options.
        if len(self) == 0: return ""
        if len(self) == 1: return str(self[0])
        
        #Filtering out any invalid passages
        passagelist = [p for p in self if p.is_valid()]
        if len(passagelist) == 0: return ""

        #Group by consecutive passages with same book
        groups = []; i=0;
        while i < len(passagelist):
            group_start = i; book = passagelist[i].start_book_n
            while i+1 < len(passagelist) and passagelist[i+1].start_book_n == book:
                i += 1
            group_end = i
            groups.append(passagelist[group_start:group_end+1])
            i += 1
        
        #Create strings for each group (of consecutive passages within the same book)
        group_strings = [];
        for group in groups:
            if group[0].bd.number_chapters[group[0].start_book_n] == 1:
                #Group of reference(s) from a single-chapter book
                parts = []
                for p in group:
                    if p.start_verse == p.end_verse:
                        parts.append(str(p.start_verse))
                    else:
                        parts.append(str(p.start_verse) + dash + str(p.end_verse))
                group_strings.append(group[0].book_name(abbreviated) + " " + ", ".join(parts))
            else:
                #Group of references from multi-chapter book
                if (len(group) == 1 and group[0].complete_book() == 1.0):
                    #Special case where there is only one reference in bunch, and that reference is for a whole book.
                    group_strings.append(group[0].book_name(abbreviated))
                else:
                    #For readability and simplicity, this part of the algorithm is within the MCBGroup class
                    bunched = MCBGroup()
                    for p in group: bunched.add(p)
                    group_strings.append(bunched.reference_string(abbreviated, dash))

        #Return completed string
        return "; ".join(group_strings)
    
    def __add__(self,other):
        """
        x.__add__(y) <==> x + y
        Addition of PassageCollection objects
        """
        if isinstance(other,Passage):
            return PassageCollection(self,other)
        elif isinstance(other,PassageCollection):
            return PassageCollection(self,other)
        else:
            return NotImplemented
        
    def append(self, passage):
        """ Add a passage to the end of the collection """
        if isinstance(passage, Passage): super(PassageCollection, self).append(passage)

    def extend(self, L):
        """ Extend the collection by appending all the items in the given list """
        if isinstance(L, PassageCollection):
            super(PassageCollection, self).extend(L.passages)
        else:
            super(PassageCollection, self).extend(L)

    def insert(self, i, passage):
        """ Insert passage at a given position """
        if isinstance(passage, Passage): super(PassageCollection, self).insert(i, passage)

    def __str__(self):
        """
        x.__str__() <==> str(x)
        Return passage string
        """
        return self.reference_string()
    
    def __unicode__(self):
        """
        x.__unicode__() <==> unicode(x)
        Return unicode version of passage string. Uses en-dash for ranges.
        """
        return unicode(self.reference_string(dash=u"–"))
    
    def abbr(self):
        """
        Return abbreviated passage string
        """
        return self.reference_string(abbreviated=True)
    
    def uabbr(self):
        """
        Return unicode-type abbreviated passage string. Uses en-dash for ranges.
        """
        return unicode(self.reference_string(abbreviated=True, dash=u"–"))
    
    def __repr__(self):
        """
        x.__repr__() <==> x
        """
        return "PassageCollection(" + ", ".join([repr(x) for x in self]) + ")"


class PassageDelta(object):
    """
    Extension (or contraction) of passages, in chapter or verse increments.
    """
    def __init__(self, chapters=0, verses=0, passage_end=True):
        """
        PassageDelta initialisation.
        To add (or remove) chapters and/or verses to the END of a passage, set passage_end=True.
        To add (or remove) chapters and/or verses to the START of a passage, set passage_end=False.
        """
        self.passage_end = passage_end
        self.delta_chapter = chapters
        self.delta_verse = verses

    def __add__(self,other):
        """
        x.__add__(y) <==> x + y
        Addition of Passage and PassageDelta objects
        """
        if isinstance(other,Passage):
            if self.passage_end:
                #Check whether passage currently finishes at the end of a chapter
                if other.end_verse == other.bd.last_verses[other.start_book_n, other.end_chapter]:
                    finishes_at_end_of_chapter = True
                else:
                    finishes_at_end_of_chapter = False
                # Compute chapter difference operation first
                (end_book_n,
                    end_chapter,
                    end_verse) = delta_chapter(self.delta_chapter,
                                                other.start_book_n, #other.end_book_n
                                                other.end_chapter,
                                                other.end_verse,
                                                other.bd,
                                                finishes_at_end_of_chapter=finishes_at_end_of_chapter)
                # Verse difference operation
                (end_book_n,
                    end_chapter,
                    end_verse) = delta_verse(self.delta_verse,
                                                end_book_n,
                                                end_chapter,
                                                end_verse,
                                                other.bd)

                return Passage(other.start_book_n, #other.start_book_n
                                other.start_chapter,
                                other.start_verse,
                                #end_book_n,
                                end_chapter,
                                end_verse)
            else:
                # Compute chapter difference operation first
                (start_book_n,
                    start_chapter,
                    start_verse) = delta_chapter(-self.delta_chapter,
                                                    other.start_book_n, #other.start_book_n
                                                    other.start_chapter,
                                                    other.start_verse,
                                                    other.bd)
                # Verse difference operation
                (start_book_n,
                    start_chapter,
                    start_verse) = delta_verse(-self.delta_verse,
                                                    start_book_n,
                                                    start_chapter,
                                                    start_verse,
                                                    other.bd)
                
                return Passage(start_book_n, 
                                start_chapter,
                                start_verse,
                                #other.end_book_n,
                                other.end_chapter,
                                other.end_verse)
        else:
            return NotImplemented

    def __radd__(self,other):
        return self.__add__(other)

    def __repr__(self):
        """
        x.__repr__() <==> x
        """
        return "PassageDelta(chapters="+repr(self.delta_chapter)+", verses="+repr(self.delta_verse)+", passage_end="+repr(self.passage_end)+")"


def delta_chapter(chapter_difference, current_book_n, current_chapter, current_verse, bible_data, finishes_at_end_of_chapter=False):
    new_chapter = current_chapter + chapter_difference
    if new_chapter > bible_data.number_chapters[current_book_n]:
        overflow_chapters = new_chapter - bible_data.number_chapters[current_book_n]
        return delta_chapter(overflow_chapters, current_book_n+1, 0, current_verse, bible_data, finishes_at_end_of_chapter)
    else:
        if finishes_at_end_of_chapter or current_verse > bible_data.last_verses[current_book_n, new_chapter]:
            current_verse = bible_data.last_verses[current_book_n, new_chapter]
        return (current_book_n, new_chapter, current_verse)


def delta_verse(verse_difference, current_book_n, current_chapter, current_verse, bible_data):
    new_verse = current_verse + verse_difference
    if new_verse > bible_data.last_verses[current_book_n, current_chapter]:
        overflow_verses =  new_verse - bible_data.last_verses[current_book_n, current_chapter]
        if current_chapter == bible_data.number_chapters[current_book_n]:
            return delta_verse(overflow_verses, current_book_n+1, 0, current_verse, bible_data)
        else:
            return delta_verse(overflow_verses, current_book_n, current_chapter+1, 0, bible_data)
    elif new_verse < 1:
        last_v_prev_chapter = bible_data.last_verses[current_book_n, current_chapter-1]
        return delta_verse(new_verse, current_book_n, current_chapter-1, last_v_prev_chapter, bible_data)
    else:
        return (current_book_n, current_chapter, new_verse)



# === Internal functions ===

class MCBGroup(object):
    """
    Internal-use class for creating reference strings for groups of passages that are all from the same multi-chapter book
    """
    def __init__(self):
        self.bunches = defaultdict(lambda: []) #Dictionary of reference objects (each within a list), indexed by order that they were added
        self.full_chapter_bunch = defaultdict(lambda: False) #Boolean indicating whether corresponding self.bunches reference is for a full chapter
        self.order = 0
        self.last_full_chapter_loc = -1 #Order of last full-chapter reference
        self.last_partial_chapter = [None, -1] #[chapter, order] of last reference that wasn't a full chapter
        
    def add(self, reference):
        #Set the book_n variable if this is the first passage added
        if self.order == 0:
            self.start_book_n = reference.start_book_n
        else:
            if reference.start_book_n != self.start_book_n: raise Exception
        
        if reference.complete_chapter(multiple=True):
            #Reference is one or more full chapters in length
            if self.last_full_chapter_loc >= 0:
                #Last reference was a full chapter, so add it to previous 'bunch'
                self.bunches[self.last_full_chapter_loc].append(reference)
            else:
                #Add new bunch
                self.bunches[self.order].append(reference)
                self.last_full_chapter_loc = self.order
                self.full_chapter_bunch[self.order] = True
            #Reset last_partial_chapter
            self.last_partial_chapter = [None, -1]
        else:
            #Reference is not a full-chapter length passage
            if reference.start_chapter == reference.end_chapter:
                #Some verse range that is within the same chapter
                if reference.start_chapter == self.last_partial_chapter[0]:
                    #Same chapter as for last passage, so add to previous bunch
                    self.bunches[self.last_partial_chapter[1]].append(reference)
                else:
                    #Different to last passage
                    self.bunches[self.order].append(reference)
                    self.last_partial_chapter = [reference.start_chapter, self.order]
            else:
                #Verse range over two or more chapters, between arbitrary verses (e.g. 5:2-7:28)
                self.last_partial_chapter = [None, -1]
                self.bunches[self.order].append(reference)
            self.last_full_chapter_loc = -1
        self.order += 1
        
    def reference_string(self, abbreviated, dash):
        if self.order == 0:
            #No passages have been added to bunch; return blank.
            return ""

        #Helper functions
        def full_ch_ref(reference, verse_encountered):
            #Chapter string for references that are one or many full chapters
            if verse_encountered:
                if reference.start_chapter == reference.end_chapter:
                    return str(reference.start_chapter) + ":" + str(reference.start_verse) + dash + str(reference.end_verse)
                else:
                    return str(reference.start_chapter) + ":" + str(reference.start_verse) + dash + str(reference.end_chapter) + ":" + str(reference.end_verse)
            else:
                if reference.start_chapter == reference.end_chapter:
                    return str(reference.start_chapter)
                else:
                    return str(reference.start_chapter) + dash + str(reference.end_chapter)
        def verses_only(reference):
            #Verse string
            if reference.start_verse == reference.end_verse:
                return str(reference.start_verse)
            else:
                return str(reference.start_verse) + dash + str(reference.end_verse)

        #List of passage bunches, sorted by order-of-addition
        ordered_bunches = sorted(self.bunches.items(), cmp=lambda x,y: cmp(x[0], y[0]) )
        
        #Iterate through bunches, creating their textual representations
        textual_bunches = []
        verse_encountered = False
        for order, bunch in ordered_bunches:
            if self.full_chapter_bunch[order]:
                #All passages in this bunch are for full chapters
                    textual_bunches.append(", ".join([full_ch_ref(x, verse_encountered) for x in bunch]))
            else:
                #Not a full-chapter bunch.
                verse_encountered = True
                if len(bunch) == 1:
                    #NB: this bunch may be over two or more chapters
                    if bunch[0].start_chapter == bunch[0].end_chapter:
                        textual_bunches.append(str(bunch[0].start_chapter) + ":" + verses_only(bunch[0]))
                    else:
                        textual_bunches.append(str(bunch[0].start_chapter) + ":" + str(bunch[0].start_verse) + dash + str(bunch[0].end_chapter) + ":" + str(bunch[0].end_verse))
                    pass
                else:
                    #Guaranteed (via self.add() algorithm) to be within same chapter
                    textual_bunches.append(", ".join([str(bunch[0].start_chapter) + ":" + verses_only(x) for x in bunch]))
        if abbreviated:
            book = bibledata.book_names[self.start_book_n][2]
        else:
            book = bibledata.book_names[self.start_book_n][1]
        return book + " " + ", ".join(textual_bunches)


def check_reference(book_n, bd, start_chapter=None, start_verse=None, end_chapter=None, end_verse=None):
    """
    Check and normalise numeric reference inputs (start_chapter, start_verse, end_chapter and end_verse)
    Where possible, missing inputs will be inferred. Thus for example, if start_chapter and end_chapter
    are provided but start_verse and end_verse are not, it will be assumed that the whole chapter was intended.
    """

    #Check which numbers have been provided.
    sc = sv = ec = ev = True
    if start_chapter == None: sc = False
    if start_verse == None: sv = False
    if end_chapter == None: ec = False
    if end_verse == None: ev = False

    #Require that numbers are not negative.
    if (sc and start_chapter < 1) or (sv and start_verse < 1) or (ec and end_chapter < 1) or (ev and end_verse < 1):
        raise InvalidPassageException("Reference cannot include negative numbers")

    #Now fill out missing information.

    #No chapter/verse information at all: Assume reference was for full book
    if not sc and not sv and not ec and not ev:
        start_chapter = start_verse = 1
        end_chapter = bd.number_chapters[book_n]
        end_verse = bd.last_verses[book_n, end_chapter]
        return (start_chapter, start_verse, end_chapter, end_verse)

    if bd.number_chapters[book_n] == 1:
        #Checks for single-chapter books
        
        if not sc and not sv:
            #No start information at all; assume 1
            start_chapter = start_verse = 1
            sc = sv = True

        if sv and ev and (not sc or start_chapter == 1) and (not ec or end_chapter == 1):
            #Verse range provided properly; start or end chapters either
            #correct (i.e., 1) or missing
            start_chapter = end_chapter = 1
        elif sc and ec and not sv and not ev:
            #Chapter range provided, when it should have been verse range (useful for parsers)
            start_verse = start_chapter
            end_verse = end_chapter
            start_chapter = end_chapter = 1
        elif sc and not ec and not ev:
            #No end chapter or verse provided
            if sv:
                #Start chapter and start verse have been provided. Interpret this as a verse *range*.
                #That is, Passage('Phm',3,6) will be interpreted as Phm 1:3-6
                end_verse = start_verse
                start_verse = start_chapter
                start_chapter = end_chapter = 1
            else:
                #Only start chapter has been provided, but because this is a single-chapter book,
                #this is equivalent to a single-verse reference
                end_verse = start_verse = start_chapter
                start_chapter = end_chapter = 1
        elif sv and not sc and not ec and not ev:
            #Only start verse entered
            end_verse = start_verse
            start_chapter = end_chapter = 1
        else:
            raise InvalidPassageException()
        
    else:
        #Checks for multi-chapter books. There are fewer valid ways to enter these references than for single-chapter books!

        #If start chapter or start_verse are missing, assume 1
        if not sc: start_chapter = 1
        if not sv: start_verse = 1

        #If end chapter is missing, we must assume it is the same as the start chapter (which hopefully is not missing)
        if not ec:
            end_chapter = start_chapter

        #If end verse is missing, we need to do some more digging
        if not ev:
            if start_chapter == end_chapter:
                #Single-chapter reference
                if sv:
                    #Start verse was provided; assume reference is a single-verse reference
                    end_verse = start_verse
                else:
                    #Neither start verse or end verse were provided. start_verse has already
                    #been set to 1 above; set end_verse to be the last verse of the chapter.
                    end_verse = bd.last_verses.get((book_n, end_chapter),1)
                    #NB: if chapter doesn't exist, passage won't be valid anyway
            else:
                #Multi-chapter reference
                #Start by truncating end_chapter if necessary
                if end_chapter > bd.number_chapters[book_n]:
                    end_chapter = bd.number_chapters[book_n]
                    #NB: if start chapter doesn't exist, passage won't be valid anyway
                #Assume end_verse is equal to the last verse of end_chapter
                end_verse = bd.last_verses[book_n, end_chapter]

    #Check that end chapter and end verse are both valid; truncate if necessary
    if end_chapter > bd.number_chapters[book_n]:
        end_chapter = bd.number_chapters[book_n]
        end_verse = bd.last_verses[book_n, end_chapter]
    elif end_verse > bd.last_verses[book_n, end_chapter]:
        end_verse = bd.last_verses[book_n, end_chapter]

    #Check that neither the start or end verses are "missing verses"; shorten if not
    if start_chapter == end_chapter:
        #Single-chapter reference
        missing = bd.missing_verses.get((book_n, start_chapter),[])
        while start_verse in missing:
            if start_verse < end_verse:
                start_verse += 1
            else: raise InvalidPassageException()
        while end_verse in missing:
            end_verse -= 1
    else:
        missing_start = bd.missing_verses.get((book_n, start_chapter),[])
        while start_verse in missing_start:
            start_verse += 1
        missing_end = bd.missing_verses.get((book_n, end_chapter),[])
        while end_verse in missing_end:
            end_verse -= 1
        if end_verse < 1:
            end_chapter -= 1
            end_verse = bd.last_verses[book_n, end_chapter]
        
    #Finished checking passage; return normalised values
    return (start_chapter, start_verse, end_chapter, end_verse)


class InvalidPassageException(Exception):
    pass


def bible_data(translation):
    """ Private method to return bible-data module corresponding to given translation """
    if translation == "ESV":
        return bibledata.esv
    else:
        return bibledata.esv


if __name__ == "__main__":
    import doctest
    doctest.testmod()

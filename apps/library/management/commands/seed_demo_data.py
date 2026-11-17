"""
Management command to populate the BookNest application with realistic,
high-quality demonstration data for showcasing the library management system.

Creates:
- 10 literary categories
- 40 realistic book records across all genres
- 20 synthetic reader profiles with contact information
- 25 circulation borrowing records (10 active, 5 overdue, 10 returned)

Idempotent: Safe to execute repeatedly without generating duplicate entities
or corrupting inventory totals.
"""

from datetime import date, timedelta
from typing import Dict, List, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.library.models import Book, BorrowRecord, Category, Reader
from apps.library.services.borrowing import issue_book, return_book


class Command(BaseCommand):
    help = (
        "Seed BookNest database with 10 categories, 40 books, 20 readers, "
        "and 25 borrowing records (active, overdue, and returned)."
    )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))
        self.stdout.write(self.style.MIGRATE_HEADING("  BookNest — Seeding Comprehensive Demo & Portfolio Dataset"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))

        try:
            with transaction.atomic():
                cat_created, cat_existing = self._seed_categories()
                book_created, book_existing = self._seed_books()
                reader_created, reader_existing = self._seed_readers()
                loan_stats = self._seed_borrowing_records()

            self._print_summary(
                cat_created, cat_existing,
                book_created, book_existing,
                reader_created, reader_existing,
                loan_stats
            )
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Error seeding demo data: {exc}"))
            raise exc

    def _seed_categories(self) -> Tuple[int, int]:
        categories_data = [
            ("Fiction & Literature", "Classic and contemporary literary novels, short stories, and prose fiction."),
            ("Science Fiction & Fantasy", "Speculative fiction, epic fantasy, futuristic worldbuilding, and cyberpunk."),
            ("Mystery & Thriller", "Crime fiction, detective investigations, psychological suspense, and legal thrillers."),
            ("Historical Fiction", "Narrative epics set within accurately researched historical epochs."),
            ("Biography & Memoir", "Personal memoirs, historical biographies, and accounts of notable figures."),
            ("Science & Technology", "Computer science, physics, astronomy, software engineering, and mathematics."),
            ("Philosophy & Ethics", "Moral philosophy, existentialism, political theory, and logic."),
            ("Art, Architecture & Design", "Visual arts, typography, urban planning, industrial design, and aesthetics."),
            ("Psychology & Human Behavior", "Cognitive science, behavioural psychology, human motivation, and habit formation."),
            ("Economics & Business", "Macroeconomics, financial systems, management strategy, and venture creation."),
        ]

        created_count = 0
        existing_count = 0

        for name, description in categories_data:
            _, created = Category.objects.get_or_create(
                name=name,
                defaults={"description": description},
            )
            if created:
                created_count += 1
            else:
                existing_count += 1

        return created_count, existing_count

    def _seed_books(self) -> Tuple[int, int]:
        # Mapping categories to 4 curated book titles each
        books_data = [
            # 1. Fiction & Literature
            {
                "category": "Fiction & Literature",
                "title": "To Kill a Mockingbird",
                "author": "Harper Lee",
                "isbn": "9780060935467",
                "publication_date": date(1960, 7, 11),
                "total_copies": 4,
                "description": "A timeless classic exploring racial injustice and the destruction of innocence in the American South through the eyes of young Scout Finch.",
            },
            {
                "category": "Fiction & Literature",
                "title": "The Great Gatsby",
                "author": "F. Scott Fitzgerald",
                "isbn": "9780743273565",
                "publication_date": date(1925, 4, 10),
                "total_copies": 3,
                "description": "A critique of the American Dream set in the lavish Roaring Twenties, chronicling the enigmatic Jay Gatsby and his obsession with Daisy Buchanan.",
            },
            {
                "category": "Fiction & Literature",
                "title": "One Hundred Years of Solitude",
                "author": "Gabriel García Márquez",
                "isbn": "9780060883287",
                "publication_date": date(1967, 5, 30),
                "total_copies": 3,
                "description": "The multi-generational saga of the Buendía family in the mythical town of Macondo, blending magical realism with Colombian history.",
            },
            {
                "category": "Fiction & Literature",
                "title": "Pride and Prejudice",
                "author": "Jane Austen",
                "isbn": "9780141439518",
                "publication_date": date(1813, 1, 28),
                "total_copies": 5,
                "description": "A witty romantic novel tracking the emotional development of Elizabeth Bennet as she navigates societal expectations and Mr. Darcy.",
            },

            # 2. Science Fiction & Fantasy
            {
                "category": "Science Fiction & Fantasy",
                "title": "Dune",
                "author": "Frank Herbert",
                "isbn": "9780441172719",
                "publication_date": date(1965, 8, 1),
                "total_copies": 5,
                "description": "Set on the desert planet Arrakis, young Paul Atreides navigates political intrigue, ecological religion, and destiny over the vital spice melange.",
            },
            {
                "category": "Science Fiction & Fantasy",
                "title": "Neuromancer",
                "author": "William Gibson",
                "isbn": "9780441569595",
                "publication_date": date(1984, 7, 1),
                "total_copies": 3,
                "description": "The definitive cyberpunk novel introducing the cyberspace matrix, following washed-up computer hacker Case on a perilous corporate heist.",
            },
            {
                "category": "Science Fiction & Fantasy",
                "title": "The Fellowship of the Ring",
                "author": "J.R.R. Tolkien",
                "isbn": "9780547928210",
                "publication_date": date(1954, 7, 29),
                "total_copies": 6,
                "description": "The opening chapter of the epic fantasy masterwork as Frodo Baggins sets out from the Shire on a perilous quest to destroy the One Ring.",
            },
            {
                "category": "Science Fiction & Fantasy",
                "title": "Foundation",
                "author": "Isaac Asimov",
                "isbn": "9780553293357",
                "publication_date": date(1951, 5, 1),
                "total_copies": 4,
                "description": "Psychohistorian Hari Seldon foresees the fall of the Galactic Empire and creates an intellectual sanctuary to preserve human civilization.",
            },

            # 3. Mystery & Thriller
            {
                "category": "Mystery & Thriller",
                "title": "The Hound of the Baskervilles",
                "author": "Arthur Conan Doyle",
                "isbn": "9780140437867",
                "publication_date": date(1902, 3, 25),
                "total_copies": 4,
                "description": "Sherlock Holmes and Dr. Watson investigate the legendary curse of a demonic hound stalking the Baskerville lineage on Dartmoor.",
            },
            {
                "category": "Mystery & Thriller",
                "title": "And Then There Were None",
                "author": "Agatha Christie",
                "isbn": "9780062073488",
                "publication_date": date(1939, 11, 6),
                "total_copies": 4,
                "description": "Ten strangers are lured to an isolated island mansion off the Devon coast and murdered one by one according to a nursery rhyme.",
            },
            {
                "category": "Mystery & Thriller",
                "title": "The Girl with the Dragon Tattoo",
                "author": "Stieg Larsson",
                "isbn": "9780307454546",
                "publication_date": date(2005, 8, 1),
                "total_copies": 3,
                "description": "Investigative journalist Mikael Blomkvist and hacker Lisbeth Salander uncover dark family secrets spanning decades of Swedish history.",
            },
            {
                "category": "Mystery & Thriller",
                "title": "The Silent Patient",
                "author": "Alex Michaelides",
                "isbn": "9781250301696",
                "publication_date": date(2019, 2, 5),
                "total_copies": 2,
                "description": "A psychological thriller about Alicia Berenson, a painter who refuses to speak a single word after allegedly shooting her husband.",
            },

            # 4. Historical Fiction
            {
                "category": "Historical Fiction",
                "title": "The Book Thief",
                "author": "Markus Zusak",
                "isbn": "9780375842207",
                "publication_date": date(2005, 9, 1),
                "total_copies": 4,
                "description": "Narrated by Death, the story follows Liesel Meminger, a young girl living near Munich during World War II who finds solace in books.",
            },
            {
                "category": "Historical Fiction",
                "title": "All the Light We Cannot See",
                "author": "Anthony Doerr",
                "isbn": "9781476746586",
                "publication_date": date(2014, 5, 6),
                "total_copies": 3,
                "description": "The intertwining paths of Marie-Laure, a blind French girl, and Werner Pfennig, a radio-engineering German orphan in occupied Saint-Malo.",
            },
            {
                "category": "Historical Fiction",
                "title": "The Pillars of the Earth",
                "author": "Ken Follett",
                "isbn": "9780451166890",
                "publication_date": date(1989, 10, 5),
                "total_copies": 4,
                "description": "Set in twelfth-century feudal England, an epic revolving around the construction of a grand cathedral in the fictional town of Kingsbridge.",
            },
            {
                "category": "Historical Fiction",
                "title": "Wolf Hall",
                "author": "Hilary Mantel",
                "isbn": "9780312429980",
                "publication_date": date(2009, 4, 30),
                "total_copies": 3,
                "description": "A complex historical chronicle detailing Thomas Cromwell's meteoric rise to power in the turbulent Tudor court of King Henry VIII.",
            },

            # 5. Biography & Memoir
            {
                "category": "Biography & Memoir",
                "title": "Steve Jobs",
                "author": "Walter Isaacson",
                "isbn": "9781451648539",
                "publication_date": date(2011, 10, 24),
                "total_copies": 4,
                "description": "The comprehensive biography of Apple's co-founder, based on unprecedented interviews spanning decades of innovation and personal conviction.",
            },
            {
                "category": "Biography & Memoir",
                "title": "The Diary of a Young Girl",
                "author": "Anne Frank",
                "isbn": "9780553296983",
                "publication_date": date(1947, 6, 25),
                "total_copies": 5,
                "description": "The candid and moving diary kept by Anne Frank while hiding with her family for two years in an Amsterdam annex during Nazi occupation.",
            },
            {
                "category": "Biography & Memoir",
                "title": "Educated",
                "author": "Tara Westover",
                "isbn": "9780399590504",
                "publication_date": date(2018, 2, 20),
                "total_copies": 3,
                "description": "A powerful memoir of self-invention following a young girl who leaves her survivalist family in rural Idaho to pursue formal education.",
            },
            {
                "category": "Biography & Memoir",
                "title": "Long Walk to Freedom",
                "author": "Nelson Mandela",
                "isbn": "9780316548182",
                "publication_date": date(1994, 12, 1),
                "total_copies": 3,
                "description": "The autobiography of Nelson Mandela, documenting his early life, 27 years of imprisonment on Robben Island, and the triumph over apartheid.",
            },

            # 6. Science & Technology
            {
                "category": "Science & Technology",
                "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
                "author": "Robert C. Martin",
                "isbn": "9780132350884",
                "publication_date": date(2008, 8, 1),
                "total_copies": 5,
                "description": "A foundational software engineering treatise outlining pragmatic principles, refactoring techniques, and naming patterns for robust code.",
            },
            {
                "category": "Science & Technology",
                "title": "Design Patterns: Elements of Reusable Object-Oriented Software",
                "author": "Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides",
                "isbn": "9780201633610",
                "publication_date": date(1994, 10, 31),
                "total_copies": 4,
                "description": "The seminal Gang of Four text presenting 23 classic architectural software patterns for extensible and maintainable systems.",
            },
            {
                "category": "Science & Technology",
                "title": "A Brief History of Time",
                "author": "Stephen Hawking",
                "isbn": "9780553380163",
                "publication_date": date(1988, 9, 1),
                "total_copies": 4,
                "description": "A landmark theoretical physics exploration of cosmology, black holes, the Big Bang, and the elusive quest for a unified theory of the universe.",
            },
            {
                "category": "Science & Technology",
                "title": "Structure and Interpretation of Computer Programs",
                "author": "Harold Abelson, Gerald Jay Sussman",
                "isbn": "9780262510875",
                "publication_date": date(1996, 7, 25),
                "total_copies": 2,
                "description": "The iconic MIT introductory computer science textbook teaching abstraction, recursion, interpretation, and computational computational models.",
            },

            # 7. Philosophy & Ethics
            {
                "category": "Philosophy & Ethics",
                "title": "Meditations",
                "author": "Marcus Aurelius",
                "isbn": "9780140449334",
                "publication_date": date(2006, 4, 27),
                "total_copies": 5,
                "description": "Private personal reflections and Stoic philosophical musings on duty, self-discipline, mortality, and tranquility by the Roman Emperor.",
            },
            {
                "category": "Philosophy & Ethics",
                "title": "The Republic",
                "author": "Plato",
                "isbn": "9780140455113",
                "publication_date": date(2007, 5, 31),
                "total_copies": 4,
                "description": "Socrates and his interlocutors engage in dialectic inquiries regarding justice, the ideal city-state, the theory of Forms, and the philosopher king.",
            },
            {
                "category": "Philosophy & Ethics",
                "title": "Beyond Good and Evil",
                "author": "Friedrich Nietzsche",
                "isbn": "9780140449235",
                "publication_date": date(2003, 1, 30),
                "total_copies": 3,
                "description": "A piercing critique of traditional moral philosophies, proposing a radical revaluation of European values and the will to power.",
            },
            {
                "category": "Philosophy & Ethics",
                "title": "Justice: What's the Right Thing to Do?",
                "author": "Michael J. Sandel",
                "isbn": "9780374532505",
                "publication_date": date(2010, 8, 17),
                "total_copies": 3,
                "description": "Harvard professor Michael Sandel presents a lucid examination of contemporary moral dilemmas through utilitarian, libertarian, and virtue ethics.",
            },

            # 8. Art, Architecture & Design
            {
                "category": "Art, Architecture & Design",
                "title": "The Design of Everyday Things",
                "author": "Don Norman",
                "isbn": "9780465050659",
                "publication_date": date(2013, 11, 5),
                "total_copies": 4,
                "description": "A cognitive design masterclass on why products either delight or frustrate users, highlighting affordances, signifiers, and conceptual models.",
            },
            {
                "category": "Art, Architecture & Design",
                "title": "Thinking with Type",
                "author": "Ellen Lupton",
                "isbn": "9781568989693",
                "publication_date": date(2010, 10, 6),
                "total_copies": 3,
                "description": "The definitive guide to visual communication for students and designers, exploring letters, grids, paragraphs, and typographic hierarchy.",
            },
            {
                "category": "Art, Architecture & Design",
                "title": "Ways of Seeing",
                "author": "John Berger",
                "isbn": "9780140135152",
                "publication_date": date(1972, 12, 1),
                "total_copies": 3,
                "description": "A landmark theoretical treatise analyzing how social status, gender roles, and photographic reproduction frame how humans view art.",
            },
            {
                "category": "Art, Architecture & Design",
                "title": "Architecture: Form, Space, and Order",
                "author": "Francis D.K. Ching",
                "isbn": "9781118745083",
                "publication_date": date(2014, 9, 8),
                "total_copies": 2,
                "description": "A beautifully illustrated architectural vocabulary handbook examining structural form, spatial configuration, proportion, and circulation.",
            },

            # 9. Psychology & Human Behavior
            {
                "category": "Psychology & Human Behavior",
                "title": "Thinking, Fast and Slow",
                "author": "Daniel Kahneman",
                "isbn": "9780374533557",
                "publication_date": date(2011, 10, 25),
                "total_copies": 5,
                "description": "Nobel laureate Daniel Kahneman dissects the dual machinery of human cognition: fast intuitive System 1 and slow deliberate System 2.",
            },
            {
                "category": "Psychology & Human Behavior",
                "title": "Man's Search for Meaning",
                "author": "Viktor E. Frankl",
                "isbn": "9780807014295",
                "publication_date": date(2006, 6, 1),
                "total_copies": 5,
                "description": "Psychiatrist Viktor Frankl chronicles his survival in Nazi concentration camps and introduces logotherapy—finding purpose through adversity.",
            },
            {
                "category": "Psychology & Human Behavior",
                "title": "Atomic Habits",
                "author": "James Clear",
                "isbn": "9780735211292",
                "publication_date": date(2018, 10, 16),
                "total_copies": 6,
                "description": "A comprehensive behavioral framework revealing how minuscule daily incremental changes compound into extraordinary personal transformations.",
            },
            {
                "category": "Psychology & Human Behavior",
                "title": "Influence: The Psychology of Persuasion",
                "author": "Robert B. Cialdini",
                "isbn": "9780061241895",
                "publication_date": date(2006, 12, 26),
                "total_copies": 4,
                "description": "The classic psychological study detailing the six universal principles of ethical and persuasive influence: reciprocity, consistency, social proof, and authority.",
            },

            # 10. Economics & Business
            {
                "category": "Economics & Business",
                "title": "The Wealth of Nations",
                "author": "Adam Smith",
                "isbn": "9780140432084",
                "publication_date": date(1982, 1, 28),
                "total_copies": 3,
                "description": "The foundational opus of classical economics analyzing division of labour, productivity, capital accumulation, and market dynamics.",
            },
            {
                "category": "Economics & Business",
                "title": "Zero to One: Notes on Startups, or How to Build the Future",
                "author": "Peter Thiel, Blake Masters",
                "isbn": "9780804139298",
                "publication_date": date(2014, 9, 16),
                "total_copies": 4,
                "description": "Venture capitalist Peter Thiel argues that genuine breakthroughs require creating entirely novel technological monopolies rather than incremental copies.",
            },
            {
                "category": "Economics & Business",
                "title": "Thinking in Systems: A Primer",
                "author": "Donella H. Meadows",
                "isbn": "9781603580557",
                "publication_date": date(2008, 12, 3),
                "total_copies": 4,
                "description": "An essential guide to systems thinking, feedback loops, leverage points, and resilience for solving complex organizational and societal challenges.",
            },
            {
                "category": "Economics & Business",
                "title": "Good to Great: Why Some Companies Make the Leap and Others Don't",
                "author": "Jim Collins",
                "isbn": "9780066620992",
                "publication_date": date(2001, 10, 16),
                "total_copies": 3,
                "description": "A rigorous five-year empirical study identifying the core management habits and Level 5 leadership traits that propel sustained corporate excellence.",
            },
        ]

        created_count = 0
        existing_count = 0

        # Pre-cache categories
        categories = {c.name: c for c in Category.objects.all()}

        for item in books_data:
            cat_obj = categories.get(item["category"])
            if not cat_obj:
                cat_obj, _ = Category.objects.get_or_create(name=item["category"])
                categories[item["category"]] = cat_obj

            book, created = Book.objects.get_or_create(
                isbn=item["isbn"],
                defaults={
                    "title": item["title"],
                    "author": item["author"],
                    "category": cat_obj,
                    "publication_date": item["publication_date"],
                    "total_copies": item["total_copies"],
                    "available_copies": item["total_copies"],
                    "description": item["description"],
                },
            )

            if created:
                created_count += 1
            else:
                existing_count += 1

        return created_count, existing_count

    def _seed_readers(self) -> Tuple[int, int]:
        readers_data = [
            ("Eleanor Vance", "eleanor.vance@booknest.example.com", "+1-555-0101", "124 Elmwood Terrace, Boston, MA 02115"),
            ("Arthur Pendelton", "arthur.pendelton@booknest.example.com", "+1-555-0102", "45 Baker Street, Apt 3B, New York, NY 10001"),
            ("Maya Lin-Carter", "maya.lin@booknest.example.com", "+1-555-0103", "782 Commonwealth Ave, Cambridge, MA 02138"),
            ("Julian Hayes", "julian.hayes@booknest.example.com", "+1-555-0104", "512 Oakwood Lane, Chicago, IL 60614"),
            ("Sophia Thorne", "sophia.thorne@booknest.example.com", "+1-555-0105", "903 Chestnut St, Philadelphia, PA 19107"),
            ("Marcus Brody", "marcus.brody@booknest.example.com", "+1-555-0106", "310 University Blvd, Seattle, WA 98105"),
            ("Clara Oswald-Price", "clara.price@booknest.example.com", "+1-555-0107", "15 Maple Court, Austin, TX 78701"),
            ("David Sterling", "david.sterling@booknest.example.com", "+1-555-0108", "624 Pine Ridge Rd, Denver, CO 80202"),
            ("Zoe Washington", "zoe.washington@booknest.example.com", "+1-555-0109", "440 Magnolia Drive, Atlanta, GA 30309"),
            ("Lucas Vance", "lucas.vance@booknest.example.com", "+1-555-0110", "88 Riverdale Ave, Portland, OR 97201"),
            ("Amara Patel", "amara.patel@booknest.example.com", "+1-555-0111", "215 Beacon Street, Boston, MA 02116"),
            ("Gabriel Rossi", "gabriel.rossi@booknest.example.com", "+1-555-0112", "731 Sunset Blvd, Los Angeles, CA 90026"),
            ("Hannah Abbott", "hannah.abbott@booknest.example.com", "+1-555-0113", "52 Willow Way, Minneapolis, MN 55403"),
            ("Liam Chen", "liam.chen@booknest.example.com", "+1-555-0114", "108 Fremont Ave, San Francisco, CA 94105"),
            ("Nadia Benali", "nadia.benali@booknest.example.com", "+1-555-0115", "340 Franklin Street, Washington, DC 20002"),
            ("Oliver Wright", "oliver.wright@booknest.example.com", "+1-555-0116", "92 Peachtree St, Nashville, TN 37203"),
            ("Priya Sharma", "priya.sharma@booknest.example.com", "+1-555-0117", "605 Lincoln Road, Miami, FL 33139"),
            ("Rowan Fletcher", "rowan.fletcher@booknest.example.com", "+1-555-0118", "418 Highland Ave, Salt Lake City, UT 84101"),
            ("Seraphina Frost", "seraphina.frost@booknest.example.com", "+1-555-0119", "127 St. Charles Ave, New Orleans, LA 70130"),
            ("Thomas Bennett", "thomas.bennett@booknest.example.com", "+1-555-0120", "833 Michigan Ave, Detroit, MI 48226"),
        ]

        created_count = 0
        existing_count = 0

        for full_name, email, phone, address in readers_data:
            _, created = Reader.objects.get_or_create(
                email=email,
                defaults={
                    "full_name": full_name,
                    "phone": phone,
                    "address": address,
                },
            )
            if created:
                created_count += 1
            else:
                existing_count += 1

        return created_count, existing_count

    def _seed_borrowing_records(self) -> Dict[str, int]:
        """
        Creates exactly 25 borrowing records:
        - 10 Active (On-time) loans
        - 5 Overdue active loans
        - 10 Returned loans

        Utilizes the domain borrowing service functions `issue_book()` and
        `return_book()` to guarantee database integrity, locking, and atomic
        inventory transitions.
        """
        today = timezone.localdate()

        # Definitions: (reader_email, book_isbn, loan_type, days_offset_issue, days_offset_due)
        # loan_type: 'ACTIVE', 'OVERDUE', 'RETURNED'
        loans_schedule = [
            # 10 Active On-time Loans (due_date in future)
            ("eleanor.vance@booknest.example.com", "9780060935467", "ACTIVE", 2, 12),
            ("arthur.pendelton@booknest.example.com", "9780441172719", "ACTIVE", 4, 10),
            ("maya.lin@booknest.example.com", "9780140437867", "ACTIVE", 1, 13),
            ("julian.hayes@booknest.example.com", "9780375842207", "ACTIVE", 5, 9),
            ("sophia.thorne@booknest.example.com", "9781451648539", "ACTIVE", 3, 11),
            ("marcus.brody@booknest.example.com", "9780132350884", "ACTIVE", 6, 8),
            ("clara.price@booknest.example.com", "9780140449334", "ACTIVE", 2, 12),
            ("david.sterling@booknest.example.com", "9780465050659", "ACTIVE", 4, 10),
            ("zoe.washington@booknest.example.com", "9780374533557", "ACTIVE", 1, 13),
            ("lucas.vance@booknest.example.com", "9780140432084", "ACTIVE", 3, 11),

            # 5 Overdue Active Loans (due_date in past, status ACTIVE)
            ("amara.patel@booknest.example.com", "9780743273565", "OVERDUE", 24, -10),
            ("gabriel.rossi@booknest.example.com", "9780441569595", "OVERDUE", 20, -6),
            ("hannah.abbott@booknest.example.com", "9780062073488", "OVERDUE", 28, -14),
            ("liam.chen@booknest.example.com", "9780201633610", "OVERDUE", 18, -4),
            ("nadia.benali@booknest.example.com", "9780807014295", "OVERDUE", 22, -8),

            # 10 Returned Loans (issued in past, then returned through return_book)
            ("oliver.wright@booknest.example.com", "9780060883287", "RETURNED", 35, -21),
            ("priya.sharma@booknest.example.com", "9780547928210", "RETURNED", 40, -26),
            ("rowan.fletcher@booknest.example.com", "9780307454546", "RETURNED", 30, -16),
            ("seraphina.frost@booknest.example.com", "9780451166890", "RETURNED", 25, -11),
            ("thomas.bennett@booknest.example.com", "9780399590504", "RETURNED", 28, -14),
            ("eleanor.vance@booknest.example.com", "9780140455113", "RETURNED", 45, -31),
            ("arthur.pendelton@booknest.example.com", "9781568989693", "RETURNED", 32, -18),
            ("maya.lin@booknest.example.com", "9780735211292", "RETURNED", 20, -6),
            ("julian.hayes@booknest.example.com", "9780804139298", "RETURNED", 26, -12),
            ("sophia.thorne@booknest.example.com", "9780553380163", "RETURNED", 38, -24),
        ]

        stats = {
            "active_created": 0,
            "active_existing": 0,
            "overdue_created": 0,
            "overdue_existing": 0,
            "returned_created": 0,
            "returned_existing": 0,
        }

        # Cache readers and books by unique identifiers
        readers_by_email = {r.email: r for r in Reader.objects.all()}
        books_by_isbn = {b.isbn: b for b in Book.objects.all()}

        for email, isbn, loan_type, issue_days_ago, due_days_offset in loans_schedule:
            reader = readers_by_email.get(email)
            book = books_by_isbn.get(isbn)

            if not reader or not book:
                continue

            issue_d = today - timedelta(days=issue_days_ago)
            # If offset is positive: future from today. If negative: past from today.
            due_d = today + timedelta(days=due_days_offset)

            if loan_type == "RETURNED":
                # Check for existing returned loan for this reader and book
                existing_returned = BorrowRecord.objects.filter(
                    reader=reader,
                    book=book,
                    status=BorrowRecord.STATUS_RETURNED,
                    issue_date=issue_d,
                ).first()

                if existing_returned:
                    stats["returned_existing"] += 1
                    continue

                # Issue and immediately return via domain service
                record = issue_book(
                    book=book,
                    reader=reader,
                    issue_date=issue_d,
                    due_date=due_d,
                )
                return_book(record.pk)

                # Set historical return timestamp for accurate chronological reporting
                record.returned_at = timezone.now() - timedelta(days=abs(due_days_offset) + 1)
                record.save(update_fields=["returned_at"])

                stats["returned_created"] += 1

            elif loan_type == "OVERDUE":
                # Check for existing active overdue loan
                existing_overdue = BorrowRecord.objects.filter(
                    reader=reader,
                    book=book,
                    status=BorrowRecord.STATUS_ACTIVE,
                    issue_date=issue_d,
                ).first()

                if existing_overdue:
                    stats["overdue_existing"] += 1
                    continue

                issue_book(
                    book=book,
                    reader=reader,
                    issue_date=issue_d,
                    due_date=due_d,
                )
                stats["overdue_created"] += 1

            else:  # ACTIVE (on-time)
                existing_active = BorrowRecord.objects.filter(
                    reader=reader,
                    book=book,
                    status=BorrowRecord.STATUS_ACTIVE,
                    issue_date=issue_d,
                ).first()

                if existing_active:
                    stats["active_existing"] += 1
                    continue

                issue_book(
                    book=book,
                    reader=reader,
                    issue_date=issue_d,
                    due_date=due_d,
                )
                stats["active_created"] += 1

        return stats

    def _print_summary(
        self,
        cat_created: int, cat_existing: int,
        book_created: int, book_existing: int,
        reader_created: int, reader_existing: int,
        loan_stats: Dict[str, int]
    ):
        total_books = Book.objects.count()
        total_categories = Category.objects.count()
        total_readers = Reader.objects.count()
        total_borrows = BorrowRecord.objects.count()
        active_loans = BorrowRecord.objects.filter(status=BorrowRecord.STATUS_ACTIVE).count()
        returned_loans = BorrowRecord.objects.filter(status=BorrowRecord.STATUS_RETURNED).count()
        overdue_loans = sum(1 for r in BorrowRecord.objects.filter(status=BorrowRecord.STATUS_ACTIVE) if r.is_overdue)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✓ Demo dataset synchronization finished successfully!"))
        self.stdout.write("")
        self.stdout.write(f"  {'Entity':<24} | {'Created':<10} | {'Existing':<10} | {'Database Total':<15}")
        self.stdout.write("  " + "-" * 68)
        self.stdout.write(f"  {'Categories':<24} | {cat_created:<10} | {cat_existing:<10} | {total_categories:<15}")
        self.stdout.write(f"  {'Books':<24} | {book_created:<10} | {book_existing:<10} | {total_books:<15}")
        self.stdout.write(f"  {'Reader Patrons':<24} | {reader_created:<10} | {reader_existing:<10} | {total_readers:<15}")
        self.stdout.write(f"  {'Active Loans (On-Time)':<24} | {loan_stats['active_created']:<10} | {loan_stats['active_existing']:<10} | {active_loans - overdue_loans:<15}")
        self.stdout.write(f"  {'Overdue Loans':<24} | {loan_stats['overdue_created']:<10} | {loan_stats['overdue_existing']:<10} | {overdue_loans:<15}")
        self.stdout.write(f"  {'Returned Loans':<24} | {loan_stats['returned_created']:<10} | {loan_stats['returned_existing']:<10} | {returned_loans:<15}")
        self.stdout.write(f"  {'Total Circulation Records':<24} | {sum([loan_stats['active_created'], loan_stats['overdue_created'], loan_stats['returned_created']]):<10} | {sum([loan_stats['active_existing'], loan_stats['overdue_existing'], loan_stats['returned_existing']]):<10} | {total_borrows:<15}")
        self.stdout.write("  " + "-" * 68)
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Inventory Health Check:"))
        
        # Verify available copies sum and total copies sum
        from django.db.models import Sum
        total_copies_sum = Book.objects.aggregate(Sum("total_copies"))["total_copies__sum"] or 0
        avail_copies_sum = Book.objects.aggregate(Sum("available_copies"))["available_copies__sum"] or 0
        expected_avail = total_copies_sum - active_loans

        self.stdout.write(f"  • Total copies owned:     {total_copies_sum}")
        self.stdout.write(f"  • Available copies on shelf: {avail_copies_sum}")
        self.stdout.write(f"  • Currently on loan:      {active_loans}")

        if avail_copies_sum == expected_avail:
            self.stdout.write(self.style.SUCCESS(f"  ✓ Inventory formula verified: available ({avail_copies_sum}) + borrowed ({active_loans}) == total ({total_copies_sum})"))
        else:
            self.stdout.write(self.style.WARNING(f"  ! Inventory discrepancy detected: available ({avail_copies_sum}) != expected ({expected_avail})"))

        self.stdout.write("")

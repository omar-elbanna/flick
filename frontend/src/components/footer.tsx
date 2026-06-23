export function Footer() {
  return (
    <footer className="border-t border-border mt-16">
      <div className="container py-6 text-xs text-muted-foreground flex flex-wrap items-center justify-between gap-3">
        <p>
          © {new Date().getFullYear()} Flick · a portfolio project
        </p>
        <p>
          Movie data &amp; posters by{" "}
          <a
            href="https://www.themoviedb.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground underline"
          >
            TMDB
          </a>
          {" "}·{" "}
          recommendations by OpenAI
        </p>
      </div>
    </footer>
  );
}

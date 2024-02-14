DEBUG=JEKYLL_GITHUB_TOKEN=blank PAGES_API_URL=http://0.0.0.0

default:
    @gem install jekyll bundler && bundle install

update:
    @bundle update

clean:
    @bundle exec jekyll clean

build: clean
    @${DEBUG} bundle exec jekyll build --profile --config _config.yml,.debug.yml

server: clean
    @${DEBUG} bundle exec jekyll server --livereload --config _config.yml,.debug.yml
    
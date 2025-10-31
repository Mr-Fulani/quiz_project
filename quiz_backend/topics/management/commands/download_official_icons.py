import os
import requests
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from topics.models import Topic
try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except ImportError:
    CAIROSVG_AVAILABLE = False

class Command(BaseCommand):
    help = 'Скачивает официальные PNG иконки для всех тем'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--topics',
            nargs='+',
            help='Список тем для скачивания иконок (по умолчанию все)',
        )
        parser.add_argument(
            '--delay',
            type=int,
            default=2,
            help='Задержка между запросами в секундах (по умолчанию 2)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно скачать заново все иконки, даже если они уже существуют',
        )

    def handle(self, *args, **options):
        self.stdout.write("🎨 Начинаю скачивание официальных PNG иконок...")
        
        # Папка для сохранения иконок
        icons_dir = os.path.join(settings.BASE_DIR, 'blog', 'static', 'blog', 'images', 'icons')
        os.makedirs(icons_dir, exist_ok=True)
        
        # Получаем темы для обработки
        if options['topics']:
            topics = Topic.objects.filter(name__in=options['topics'])
        else:
            topics = Topic.objects.all()
        
        self.stdout.write(f"📚 Найдено {topics.count()} тем для обработки")
        
        downloaded_count = 0
        skipped_count = 0
        error_count = 0
        force_download = options['force']
        
        for i, topic in enumerate(topics):
            self.stdout.write(f"\n🔍 Обрабатываю тему: {topic.name}")
            
            # Проверяем, есть ли уже PNG иконка
            png_filename = f"{topic.name.lower().replace(' ', '-').replace('.', '').replace('#', 'sharp')}-icon.png"
            png_path = os.path.join(icons_dir, png_filename)
            
            # Проверяем, есть ли уже официальная PNG иконка
            if not force_download and os.path.exists(png_path):
                # Проверяем размер файла - если больше 1000 байт, скорее всего это официальная иконка
                file_size = os.path.getsize(png_path)
                if file_size > 1000:
                    self.stdout.write(f"  ✅ Официальная PNG иконка уже существует: {png_filename} ({file_size} байт)")
                    skipped_count += 1
                    continue
                else:
                    self.stdout.write(f"  🔄 Заменяю самодельную/пустую иконку на официальную: {png_filename} ({file_size} байт)")
                    os.remove(png_path)  # Удаляем самодельную/пустую иконку
            elif force_download and os.path.exists(png_path):
                self.stdout.write(f"  🔥 Принудительная перезапись для: {png_filename}")
            
            # Скачиваем официальную иконку
            success = self.download_official_icon(topic.name, png_path)
            
            if success:
                # Обновляем путь к иконке в БД
                topic.icon = f'/static/blog/images/icons/{png_filename}'
                topic.save()
                self.stdout.write(f"  ✅ Скачана официальная PNG иконка: {png_filename}")
                downloaded_count += 1
            else:
                self.stdout.write(f"  ❌ Не удалось скачать иконку для: {topic.name}")
                error_count += 1
            
            # Задержка между запросами
            if i < topics.count() - 1:  # Не ждем после последнего
                time.sleep(options['delay'])
        
        self.stdout.write(f"\n📊 Итоговая статистика:")
        self.stdout.write(f"  - Всего тем: {topics.count()}")
        self.stdout.write(f"  - Скачано иконок: {downloaded_count}")
        self.stdout.write(f"  - Пропущено: {skipped_count}")
        self.stdout.write(f"  - Ошибок: {error_count}")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Скачивание официальных иконок завершено!"))

    def download_official_icon(self, topic_name, output_path):
        """Скачивает официальную PNG иконку для темы"""
        
        # URL для devicons
        devicon_name = topic_name.lower().replace(' ', '').replace('.', '').replace('#', 'sharp').replace('+', 'plus')
        devicon_url = f'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/{devicon_name}/{devicon_name}-original.svg'
        
        # Сначала пытаемся скачать SVG из devicons и конвертировать в PNG
        try:
            response = requests.get(devicon_url, stream=True, timeout=15)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '')
            if 'image/svg' in content_type:
                if CAIROSVG_AVAILABLE:
                    try:
                        png_data = cairosvg.svg2png(bytestring=response.content, output_width=64, output_height=64)
                        with open(output_path, 'wb') as f:
                            f.write(png_data)
                        
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                            self.stdout.write(f"    ✅ Успешно скачано и конвертировано из devicons")
                            return True
                    except Exception as e:
                        self.stdout.write(f"    ❌ Ошибка конвертации SVG из devicons: {e}")
                else:
                    self.stdout.write(f"    ⚠️  cairosvg не установлен, не могу конвертировать SVG из devicons")
        except Exception as e:
            self.stdout.write(f"    ℹ️  Не удалось скачать с devicons: {e}")

        # Если devicons не сработал, используем старый список официальных URL
        self.stdout.write(f"    ℹ️  Пробую найти по официальному URL...")
        # Специальные URL для известных технологий (используем простые и надежные источники)
        official_urls = {
            'Python': 'https://www.python.org/static/img/python-logo.png',
            'JavaScript': 'https://upload.wikimedia.org/wikipedia/commons/6/6a/JavaScript-logo.png',
            'React': 'https://upload.wikimedia.org/wikipedia/commons/a/a7/React-icon.svg',
            'Node.js': 'https://nodejs.org/static/images/logo.png',
            'Vue.js': 'https://vuejs.org/images/logo.png',
            'Angular': 'https://angular.io/assets/images/logos/angular/angular.png',
            'TypeScript': 'https://upload.wikimedia.org/wikipedia/commons/4/4c/Typescript_logo_2020.svg',
            'PHP': 'https://www.php.net/images/logos/php-logo-white.png',
            'Java': 'https://www.java.com/assets/images/java-logo-icon.png',
            'C++': 'https://upload.wikimedia.org/wikipedia/commons/1/18/ISO_C%2B%2B_Logo.svg',
            'C#': 'https://upload.wikimedia.org/wikipedia/commons/4/4f/Csharp_Logo.png',
            'Ruby': 'https://www.ruby-lang.org/images/logo.png',
            'Go': 'https://go.dev/blog/go-brand/Go-Logo/PNG/Go-Logo_Blue.png',
            'Rust': 'https://www.rust-lang.org/logos/rust-logo-blk.png',
            'Swift': 'https://developer.apple.com/assets/elements/icons/swift/swift-64x64.png',
            'Kotlin': 'https://kotlinlang.org/assets/images/open-graph/kotlin_250x250.png',
            'Scala': 'https://www.scala-lang.org/resources/img/scala-logo.png',
            'R': 'https://www.r-project.org/Rlogo.png',
            'MATLAB': 'https://upload.wikimedia.org/wikipedia/commons/2/21/Matlab_Logo.png',
            'Julia': 'https://julialang.org/assets/img/logos/logo-square.png',
            'HTML': 'https://www.w3.org/html/logo/downloads/HTML5_Logo_256.png',
            'CSS': 'https://cdn.worldvectorlogo.com/logos/css-3.svg',
            'Sass': 'https://sass-lang.com/assets/img/logos/logo-b6e1ef6e.svg',
            'Less': 'https://lesscss.org/public/img/less_logo.png',
            'Bootstrap': 'https://getbootstrap.com/docs/5.3/assets/brand/bootstrap-logo-shadow.png',
            'Tailwind CSS': 'https://tailwindcss.com/_next/static/media/social-square.b622e290.jpg',
            'Material-UI': 'https://mui.com/static/logo.png',
            'Redux': 'https://redux.js.org/img/redux.svg',
            'Vuex': 'https://vuex.vuejs.org/logo.png',
            'MobX': 'https://mobx.js.org/img/mobx.png',
            'GraphQL': 'https://graphql.org/img/logo.svg',
            'REST API': 'https://www.vectorlogo.zone/logos/getpostman/getpostman-icon.svg',
            'MongoDB': 'https://www.mongodb.com/assets/images/global/leaf.png',
            'PostgreSQL': 'https://www.postgresql.org/media/img/about/press/elephant.png',
            'MySQL': 'https://www.mysql.com/common/logos/logo-mysql-170x115.png',
            'Redis': 'https://redis.io/images/redis-white.png',
            'Elasticsearch': 'https://cdn.worldvectorlogo.com/logos/elasticsearch.svg',
            'AWS': 'https://d0.awsstatic.com/logos/powered-by-aws.png',
            'Azure': 'https://symbols.getvecta.com/stencil_25/41_azure.d8d64ad038.svg',
            'Google Cloud': 'https://cloud.google.com/_static/cloud/images/social-icon-google-cloud-1200-630.png',
            'Heroku': 'https://www.herokucdn.com/deploy/button.svg',
            'Kubernetes': 'https://kubernetes.io/images/favicon.png',
            'Jenkins': 'https://www.jenkins.io/images/logos/jenkins/jenkins.png',
            'GitLab CI': 'https://about.gitlab.com/images/press/logo/png/gitlab-icon-rgb.png',
            'GitHub Actions': 'https://github.githubassets.com/images/modules/site/features/actions-icon-64x64.png',
            'Jest': 'https://jestjs.io/img/jest.svg',
            'Cypress': 'https://raw.githubusercontent.com/cypress-io/cypress-icons/master/src/icons/icon_128x128.png',
            'Selenium': 'https://www.selenium.dev/images/selenium_logo_square_green.png',
            'Postman': 'https://www.postman.com/_assets/logos/postman-logo-icon-orange.png',
            'Insomnia': 'https://insomnia.rest/images/insomnia-logo.svg',
            'Figma': 'https://www.figma.com/static/images/og-image.png',
            'Adobe XD': 'https://www.adobe.com/content/dam/cc/icons/xd.svg',
            'Sketch': 'https://www.sketch.com/images/press/sketch-logo-square.png',
            'Django': 'https://static.djangoproject.com/img/logos/django-logo-positive.png',
            'Docker': 'https://www.docker.com/wp-content/uploads/2022/03/Moby-logo.png',
            'Git': 'https://git-scm.com/images/logos/downloads/Git-Icon-1788C.png',
            'Golang': 'https://go.dev/blog/go-brand/Go-Logo/PNG/Go-Logo_Blue.png',
            'SQL': 'https://www.mysql.com/common/logos/logo-mysql-170x115.png',
            'Dart': 'https://dart.dev/assets/img/dart-logo-horizontal.svg',
            # Популярные языки
            'Perl': 'https://upload.wikimedia.org/wikipedia/commons/a/a6/Perl_logo.svg',
            'Haskell': 'https://upload.wikimedia.org/wikipedia/commons/a/a6/Haskell-Logo.svg',
            'Elixir': 'https://elixir-lang.org/images/logo/logo.png',
            'Clojure': 'https://upload.wikimedia.org/wikipedia/commons/5/5d/Clojure_logo.svg',
            'Erlang': 'https://upload.wikimedia.org/wikipedia/commons/a/aa/Erlang_logo.svg',
            # Микросервисы и контейнеризация
            'Helm': 'https://helm.sh/img/helm.svg',
            'Prometheus': 'https://prometheus.io/assets/prometheus_logo_grey.svg',
            'Grafana': 'https://grafana.com/static/img/menu/grafana2.svg',
            'Jaeger': 'https://www.jaegertracing.io/img/jaeger-logo.svg',
            # Базы данных
            'Cassandra': 'https://cassandra.apache.org/images/cassandra_logo.png',
            'ClickHouse': 'https://clickhouse.com/press/Logo/clickhouse-logo.png',
            'InfluxDB': 'https://www.influxdata.com/wp-content/uploads/InfluxDB_logo.svg',
            'Neo4j': 'https://neo4j.com/wp-content/themes/neo4jweb/assets/images/neo4j-logo-2015.png',
            # Backend фреймворки
            'Flask': 'https://flask.palletsprojects.com/en/2.3.x/_static/flask-icon.png',
            'FastAPI': 'https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png',
            'Spring Boot': 'https://spring.io/projects/spring-boot',
            'Express.js': 'https://expressjs.com/images/express-facebook-share.png',
            'NestJS': 'https://nestjs.com/img/logo_text.svg',
            'Rails': 'https://rubyonrails.org/images/rails-logo.svg',
            'Laravel': 'https://laravel.com/img/logomark.min.svg',
            'Phoenix': 'https://www.phoenixframework.org/images/phoenix-logo.svg',
            'ASP.NET Core': 'https://dotnet.microsoft.com/static/images/redesign/social-square.png',
            # Frontend фреймворки и библиотеки
            'Svelte': 'https://svelte.dev/tutorial/introduction',
            'Next.js': 'https://nextjs.org/static/favicon/favicon-96x96.png',
            'Nuxt.js': 'https://nuxt.com/',
            'Gatsby': 'https://www.gatsbyjs.com/static/gatsby-icon-4a9773549091c227cd2eb82ccd9c5e3d.png',
            'JQuery': 'https://jquery.com/jquery-wp-content/themes/jquery/images/logo-jquery.svg',
            'Backbone.js': 'https://backbonejs.org/docs/images/backbone.png',
            'Ember.js': 'https://emberjs.com/images/brand/ember_Ember-Dark.svg',
            # Mobile
            'Flutter': 'https://flutter.dev/assets/flutter-lockup-1caf6476beed76adec3c477586da54de6ce552a2f42163ec3af4f2071f3a8395.svg',
            'React Native': 'https://reactnative.dev/img/tiny_logo.png',
            'Ionic': 'https://ionicframework.com/img/meta/favicon-96x96.png',
            'Xamarin': 'https://dotnet.microsoft.com/static/images/redesign/social-square.png',
            # Инструменты DevOps
            'Terraform': 'https://www.terraform.io/hashicorp-assets/images/logos/terraform.svg',
            'Ansible': 'https://www.ansible.com/hs-fs/hubfs/2016-red-hat-ansible-logo.png',
            'Puppet': 'https://puppet.com/images/puppet-logo.png',
            'Chef': 'https://www.chef.io/static/img/logos/chef-logo.svg',
            'GitLab': 'https://about.gitlab.com/images/press/logo/png/gitlab-logo.png',
            'Bitbucket': 'https://bitbucket.org/product/press-kit/logos/bitbucket-icon-32.png',
            # Cloud платформы
            'GCP': 'https://cloud.google.com/_static/cloud/images/social-icon-google-cloud-1200-630.png',
            'DigitalOcean': 'https://www.digitalocean.com/favicon.ico',
            'Linode': 'https://www.linode.com/wp-content/uploads/2022/01/linode-logo-red.png',
            # Мониторинг и логирование
            'ELK Stack': 'https://www.elastic.co/blogs/content/images/sized/2016-08-elk_elkheartbeat.png',
            'Logstash': 'https://www.elastic.co/logstash',
            'Kibana': 'https://www.elastic.co/kibana',
            'Splunk': 'https://www.splunk.com/content/dam/splunk2/images/homepage/splunk-logo_light-bg.svg',
            # Message brokers
            'Apache Pulsar': 'https://pulsar.apache.org/img/pulsar.svg',
            # Тестирование
            'Mocha': 'https://mochajs.org/static/mocha-logo.png',
            'Jasmine': 'https://jasmine.github.io/images/jasmine_vertical.svg',
            'Karma': 'https://karma-runner.github.io/assets/img/banner.png',
            'Protractor': 'https://raw.githubusercontent.com/angular/protractor/master/chrome/test/protractorLogo.jpg',
            'Robot Framework': 'https://robotframework.org/img/RF.svg',
            # Другое
            'Deno': 'https://deno.land/images/deno-logo-v2_2.gif',
            'Bun': 'https://bun.sh/logo.svg',
        }
        
        # Если есть официальный URL для темы
        if topic_name in official_urls:
            url = official_urls[topic_name]
            try:
                response = requests.get(url, stream=True, timeout=15)
                response.raise_for_status()
                
                # Проверяем тип контента
                content_type = response.headers.get('Content-Type', '')
                if 'image/svg' in content_type or url.endswith('.svg'):
                    # Если это SVG, конвертируем в PNG
                    if CAIROSVG_AVAILABLE:
                        try:
                            # Конвертируем SVG в PNG
                            png_data = cairosvg.svg2png(bytestring=response.content, output_width=64, output_height=64)
                            with open(output_path, 'wb') as f:
                                f.write(png_data)
                        except Exception as e:
                            self.stdout.write(f"    ❌ Ошибка конвертации SVG: {e}")
                            return False
                    else:
                        self.stdout.write(f"    ⚠️  cairosvg не установлен, пропускаю SVG для {topic_name}")
                        return False
                else:
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                
                # Проверяем, что файл скачался и не пустой
                if os.path.exists(output_path) and os.path.getsize(output_path) > 100:  # Минимум 100 байт
                    return True
                else:
                    # Удаляем пустой файл
                    if os.path.exists(output_path):
                        os.remove(output_path)
                        self.stdout.write(f"    ⚠️  Удален пустой файл для {topic_name}")
                    
            except Exception as e:
                self.stdout.write(f"    ❌ Ошибка скачивания с официального URL: {e}")
        
        # Если ничего не сработало
        return False

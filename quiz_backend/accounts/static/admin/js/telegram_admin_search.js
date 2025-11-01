(function($) {
    'use strict';
    
    $(document).ready(function() {
        const $userSearchField = $('#id_user_search');
        const $telegramIdField = $('#id_telegram_id');
        const $usernameField = $('#id_username');
        const $languageField = $('#id_language');
        const $photoField = $('#id_photo');
        
        // Проверяем, что поля существуют (на странице добавления/редактирования)
        if (!$userSearchField.length || !$telegramIdField.length) {
            return;
        }
        
        let searchTimeout;
        let $resultsContainer;
        let $searchButton;
        let $modal;
        let currentPage = 1;
        
        // Создаем контейнер для результатов поиска
        function createResultsContainer() {
            if (!$resultsContainer) {
                $resultsContainer = $('<div id="user-search-results" style="position: absolute; background: white; border: 1px solid #ddd; border-radius: 4px; max-height: 300px; overflow-y: auto; z-index: 1000; display: none; box-shadow: 0 2px 8px rgba(0,0,0,0.15);"></div>');
                $userSearchField.parent().css('position', 'relative');
                $userSearchField.parent().append($resultsContainer);
            }
            return $resultsContainer;
        }
        
        // Функция поиска пользователя
        function searchUser(query) {
            if (!query || query.length < 2) {
                $resultsContainer.hide();
                return;
            }
            
            $.ajax({
                url: '/admin/accounts/telegramadmin/search-user/',
                data: { q: query },
                dataType: 'json',
                success: function(response) {
                    displayResults(response.results || []);
                },
                error: function(xhr, status, error) {
                    console.error('Ошибка поиска:', error);
                    $resultsContainer.hide();
                }
            });
        }
        
        // Отображение результатов поиска
        function displayResults(results) {
            createResultsContainer();
            $resultsContainer.empty();
            
            if (results.length === 0) {
                $resultsContainer.html('<div style="padding: 10px; color: #999;">Пользователи не найдены</div>');
                $resultsContainer.show();
                return;
            }
            
            results.forEach(function(user) {
                const displayName = user.first_name && user.last_name 
                    ? `${user.first_name} ${user.last_name}` 
                    : user.first_name || user.username || `ID: ${user.telegram_id}`;
                
                const sourceLabel = user.source === 'TelegramUser' ? '👤 Telegram' 
                    : user.source === 'MiniAppUser' ? '📱 Mini App'
                    : '🌐 Сайт';
                
                const $item = $('<div class="user-search-item" style="padding: 10px; cursor: pointer; border-bottom: 1px solid #eee;" onmouseover="this.style.background=\'#f5f5f5\'" onmouseout="this.style.background=\'white\'"></div>');
                $item.html(`
                    <strong>${escapeHtml(displayName)}</strong>
                    ${user.username ? `<br><small style="color: #666;">@${escapeHtml(user.username)}</small>` : ''}
                    <br><small style="color: #999;">${sourceLabel} | ID: ${user.telegram_id} | Язык: ${user.language || 'ru'}</small>
                `);
                
                $item.on('click', function() {
                    selectUser(user);
                });
                
                $resultsContainer.append($item);
            });
            
            $resultsContainer.show();
        }
        
        // Выбор пользователя из результатов
        function selectUser(user) {
            $telegramIdField.val(user.telegram_id);
            $usernameField.val(user.username || '');
            $languageField.val(user.language || 'ru');
            if (user.photo) {
                $photoField.val(user.photo);
            }
            
            // Обновляем поле поиска с выбранным пользователем
            const displayName = user.first_name && user.last_name 
                ? `${user.first_name} ${user.last_name}` 
                : user.first_name || user.username || `ID: ${user.telegram_id}`;
            $userSearchField.val(`${user.telegram_id} (@${user.username || 'без username'})`);
            
            $resultsContainer.hide();
        }
        
        // Экранирование HTML
        function escapeHtml(text) {
            if (!text) return '';
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return text.replace(/[&<>"']/g, function(m) { return map[m]; });
        }
        
        // Обработка ввода в поле поиска
        $userSearchField.on('input', function() {
            const query = $(this).val().trim();
            
            clearTimeout(searchTimeout);
            
            if (query.length >= 2) {
                searchTimeout = setTimeout(function() {
                    searchUser(query);
                }, 300); // Задержка 300ms для уменьшения количества запросов
            } else {
                $resultsContainer.hide();
            }
        });
        
        // Скрываем результаты при клике вне
        $(document).on('click', function(e) {
            if (!$(e.target).closest('#id_user_search, #user-search-results').length) {
                $resultsContainer.hide();
            }
        });
        
        // Обработка клавиш (Enter, Escape)
        $userSearchField.on('keydown', function(e) {
            if (e.key === 'Escape') {
                $resultsContainer.hide();
                if ($modal && $modal.is(':visible')) {
                    closeModal();
                }
            }
        });
        
        // Находим существующую кнопку с лупой (созданную в виджете)
        function initSearchButton() {
            $searchButton = $('#user-search-button');
            if ($searchButton.length) {
                $searchButton.on('click', function(e) {
                    e.preventDefault();
                    openSubscribersModal();
                });
            }
            return $searchButton;
        }
        
        // Создаем модальное окно для списка подписчиков
        function createModal() {
            if (!$modal) {
                $modal = $(`
                    <div id="subscribers-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 10000;">
                        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; border-radius: 8px; width: 80%; max-width: 800px; max-height: 80vh; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
                            <div style="padding: 20px; border-bottom: 1px solid #ddd; background: #417690; color: white; display: flex; justify-content: space-between; align-items: center;">
                                <h3 style="margin: 0; font-size: 18px;">📋 Список подписчиков каналов</h3>
                                <button type="button" id="close-modal" style="background: transparent; border: none; color: white; font-size: 24px; cursor: pointer; padding: 0; width: 30px; height: 30px;">×</button>
                            </div>
                            <div style="padding: 15px; border-bottom: 1px solid #ddd;">
                                <input type="text" id="modal-search" placeholder="🔍 Поиск по username или ID..." style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">
                            </div>
                            <div id="modal-content" style="padding: 15px; max-height: 60vh; overflow-y: auto;">
                                <div style="text-align: center; padding: 20px; color: #999;">Загрузка...</div>
                            </div>
                            <div id="modal-pagination" style="padding: 15px; border-top: 1px solid #ddd; text-align: center; background: #f5f5f5;">
                            </div>
                        </div>
                    </div>
                `);
                $('body').append($modal);
                
                $('#close-modal').on('click', closeModal);
                $('#modal-search').on('input', function() {
                    currentPage = 1;
                    loadSubscribers();
                });
                
                // Закрытие при клике вне модального окна
                $modal.on('click', function(e) {
                    if ($(e.target).is('#subscribers-modal')) {
                        closeModal();
                    }
                });
            }
            return $modal;
        }
        
        // Открытие модального окна
        function openSubscribersModal() {
            createModal();
            currentPage = 1;
            $modal.show();
            loadSubscribers();
        }
        
        // Закрытие модального окна
        function closeModal() {
            if ($modal) {
                $modal.hide();
            }
        }
        
        // Загрузка списка подписчиков
        function loadSubscribers() {
            const searchQuery = $('#modal-search').val().trim();
            const $content = $('#modal-content');
            $content.html('<div style="text-align: center; padding: 20px; color: #999;">Загрузка...</div>');
            
            $.ajax({
                url: '/admin/accounts/telegramadmin/list-subscribers/',
                data: { 
                    page: currentPage,
                    search: searchQuery
                },
                dataType: 'json',
                success: function(response) {
                    displaySubscribers(response);
                },
                error: function(xhr, status, error) {
                    console.error('Ошибка загрузки подписчиков:', error);
                    $content.html('<div style="text-align: center; padding: 20px; color: #dc3545;">Ошибка загрузки списка подписчиков</div>');
                }
            });
        }
        
        // Отображение списка подписчиков
        function displaySubscribers(data) {
            const $content = $('#modal-content');
            const $pagination = $('#modal-pagination');
            
            if (!data.users || data.users.length === 0) {
                $content.html('<div style="text-align: center; padding: 20px; color: #999;">Подписчики не найдены</div>');
                $pagination.html('');
                return;
            }
            
            let html = '<table style="width: 100%; border-collapse: collapse;">';
            html += '<thead><tr style="background: #f5f5f5; border-bottom: 2px solid #ddd;"><th style="padding: 10px; text-align: left;">ID</th><th style="padding: 10px; text-align: left;">Имя</th><th style="padding: 10px; text-align: left;">Username</th><th style="padding: 10px; text-align: left;">Подписка</th><th style="padding: 10px; text-align: center;">Действие</th></tr></thead>';
            html += '<tbody>';
            
            data.users.forEach(function(user) {
                const displayName = (user.first_name || '') + ' ' + (user.last_name || '');
                html += `<tr style="border-bottom: 1px solid #eee;" onmouseover="this.style.background='#f9f9f9'" onmouseout="this.style.background='white'">`;
                html += `<td style="padding: 10px;">${user.telegram_id}</td>`;
                html += `<td style="padding: 10px;">${escapeHtml(displayName.trim() || '—')}</td>`;
                html += `<td style="padding: 10px;">${user.username ? '@' + escapeHtml(user.username) : '—'}</td>`;
                html += `<td style="padding: 10px; font-size: 12px; color: #666;">${user.subscribed_at || '—'}</td>`;
                html += `<td style="padding: 10px; text-align: center;"><button class="select-user-btn" data-user-id="${user.telegram_id}" data-username="${escapeHtml(user.username || '')}" data-first-name="${escapeHtml(user.first_name || '')}" data-last-name="${escapeHtml(user.last_name || '')}" data-language="${user.language || 'ru'}" style="background: #417690; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">Выбрать</button></td>`;
                html += `</tr>`;
            });
            
            html += '</tbody></table>';
            $content.html(html);
            
            // Обработчики кнопок выбора
            $('.select-user-btn').on('click', function() {
                const user = {
                    telegram_id: $(this).data('user-id'),
                    username: $(this).data('username'),
                    first_name: $(this).data('first-name'),
                    last_name: $(this).data('last-name'),
                    language: $(this).data('language')
                };
                selectUser(user);
                closeModal();
            });
            
            // Пагинация
            if (data.total > data.per_page) {
                let paginationHtml = '';
                if (data.page > 1) {
                    paginationHtml += `<button type="button" id="prev-page" style="margin-right: 10px; padding: 5px 15px; background: #417690; color: white; border: none; border-radius: 3px; cursor: pointer;">← Назад</button>`;
                }
                paginationHtml += `<span style="margin: 0 15px;">Страница ${data.page} из ${Math.ceil(data.total / data.per_page)} (всего: ${data.total})</span>`;
                if (data.has_more) {
                    paginationHtml += `<button type="button" id="next-page" style="margin-left: 10px; padding: 5px 15px; background: #417690; color: white; border: none; border-radius: 3px; cursor: pointer;">Вперёд →</button>`;
                }
                $pagination.html(paginationHtml);
                
                $('#prev-page').on('click', function() {
                    if (currentPage > 1) {
                        currentPage--;
                        loadSubscribers();
                    }
                });
                
                $('#next-page').on('click', function() {
                    if (data.has_more) {
                        currentPage++;
                        loadSubscribers();
                    }
                });
            } else {
                $pagination.html(`<span style="color: #666;">Всего: ${data.total}</span>`);
            }
        }
        
        // Инициализируем кнопку поиска (она уже создана в HTML виджетом)
        initSearchButton();
    });
})(django.jQuery || jQuery);


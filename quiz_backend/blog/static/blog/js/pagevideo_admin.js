// Динамическое отображение полей медиа в зависимости от выбранного типа
(function($) {
    'use strict';
    
    function toggleMediaFields() {
        var mediaType = $('#id_media_type').val();
        
        // Скрываем все поля медиа
        $('#id_video_url').closest('.form-row').hide();
        $('#id_video_file').closest('.form-row').hide();
        $('#id_gif').closest('.form-row').hide();
        
        // Показываем только нужное поле
        if (mediaType === 'video_url') {
            $('#id_video_url').closest('.form-row').show();
        } else if (mediaType === 'video_file') {
            $('#id_video_file').closest('.form-row').show();
        } else if (mediaType === 'gif') {
            $('#id_gif').closest('.form-row').show();
        }
    }
    
    $(document).ready(function() {
        // При загрузке страницы
        toggleMediaFields();
        
        // При изменении типа медиа
        $('#id_media_type').on('change', toggleMediaFields);
    });
})(django.jQuery);


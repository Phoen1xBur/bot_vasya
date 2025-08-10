// Инициализация Telegram WebApp
const WebApp = window.Telegram.WebApp;

// Получаем параметры из URL
const urlParams = new URLSearchParams(window.location.search);
const chatId = urlParams.get('chat_id');
const requestFunc = urlParams.get('request_func');

WebApp.ready();
WebApp.expand();

const initData = WebApp.initData;

// Функция для получения профиля пользователя для конкретного чата
async function loadUserProfileForChat() {
    const loadingElement = document.getElementById('loading');
    const profileInfoElement = document.getElementById('profile-info');
    const errorElement = document.getElementById('error');

    try {
        errorElement.style.display = 'none';
        profileInfoElement.style.display = 'none';
        loadingElement.style.display = 'block';

        // Отправляем запрос к API с параметрами чата
        const response = await fetch(`/api/user/profile?chat_id=${chatId}`, {
            method: 'GET',
            headers: {
                'Authorization': initData,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const userData = await response.json();

        loadingElement.style.display = 'none';

        // Заполняем данные профиля
        const userMention = userData.username ?
            `<a href="https://t.me/${userData.username}">@${userData.username}</a>` :
            userData.full_name;

        document.getElementById('user-mention').innerHTML = userMention;
        document.getElementById('user-balance').textContent =
            `${userData.money} ${userData.vasya_coin}`;

        profileInfoElement.style.display = 'block';

    } catch (error) {
        console.error('Ошибка загрузки профиля:', error);
        loadingElement.style.display = 'none';
        errorElement.style.display = 'block';
        errorElement.textContent = `Ошибка: ${error.message}`;
    }
}

// Загружаем профиль при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    if (!initData) {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'block';
        document.getElementById('error').textContent = 'Ошибка: нет данных авторизации';
        return;
    }

    if (!chatId) {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'block';
        document.getElementById('error').textContent = 'Ошибка: не указан чат';
        return;
    }

    loadUserProfileForChat();
});
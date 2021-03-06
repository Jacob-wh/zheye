# coding=utf-8
import base64

from flask import current_app
from flask_login import login_user, login_required, logout_user, current_user
from flask import render_template, redirect, url_for, request, flash

from app import db
from app.auth import auth
from app.auth.forms import LoginForm, RegistrationForm, ChangepasswordForm, ChangeEmailForm, InsertCategory, InsertTopic, \
    EditProfileAdminForm
from app.lib.mail.email import send_email
from app.lib.pagination import base_pagination
from app.models.models import User, TopicCategory, Topic, Role
from app.lib import constant
from app.auth.permission import admin_required, permission_required


@auth.before_app_request
def before_request():
    if current_user.is_authenticated:
        if not current_user.confirmed \
                and request.endpoint[:5] != 'auth.'\
                and request.endpoint != 'static':
            return redirect(url_for('auth.unconfirmed'))


@auth.route('/login', methods=['GET', 'POST'])
def login_register():
    login_form = LoginForm()
    register_form = RegistrationForm()
    # 进行登录表单的验证
    if login_form.submit1.data and login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()
        if user is not None and user.verify_password(login_form.password.data):
            login_user(user, login_form.remember_me.data)
            return redirect(url_for('main.index'))
        flash(constant.WRONG)

    # 进行注册表单的验证
    if register_form.submit2.data and register_form.validate_on_submit():
        user = User(email=register_form.email.data,
                    username=register_form.username.data,
                    password=register_form.password.data,
                    name=register_form.username.data)
        db.session.add(user)
        db.session.commit()
        try:
            token = user.generate_confirmation_token()
            send_email(user.email, 'Confirm Your Account',
                       'auth/email/confirm', user=user, token=token)
            flash(constant.SEND_EMIAL)
        except Exception as e:
            print e
        return redirect(url_for('auth.login_register'))

    return render_template('auth/login.html', form1=login_form, form2=register_form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        flash(constant.VERIFI_SUCCESS)
    else:
        flash(constant.LINK_FAIL)
    return redirect(url_for('main.index'))


@auth.route('/unconfirmed')
def unconfirmed():
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html', user=current_user)


@auth.route('/confirm')
@login_required
def resend_confirmation():
    """进行验证邮箱的重新发送"""
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, 'Confirm Your Account',
               'auth/email/confirm', user=current_user, token=token)
    flash(constant.SEND_EMIAL)
    return redirect(url_for('main.index'))


@auth.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    return redirect(url_for("auth.profile"))


@auth.route('/settings/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """账户邮箱设置"""
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            new_email = form.email.data
            token = current_user.generate_email_change_token(new_email)
            send_email(new_email, 'Confirm your email address',
                       'auth/email/change_email',
                       user=current_user, token=token)
            flash(constant.SEND_EMIAL)
            return redirect(url_for('auth.profile'))
        else:
            flash(constant.WRONG_PWD)
    return render_template("email_settings.html", user=current_user, form=form, base64=base64)


@auth.route('/change-email/<token>')
@login_required
def change_email(token):
    if current_user.change_email(token):
        flash(constant.EMAIL_UPDATE)
    else:
        flash(constant.UPDATE_FAIL)
    return redirect(url_for('auth.profile'))


@auth.route('/settings/password', methods=['GET', 'POST'])
@login_required
def password():
    """用户密码设置"""
    form = ChangepasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.oldpassword.data):
            if current_user.change_password(form.password.data):
                flash(constant.UPDATE_SUCC)
                logout_user()
                return redirect(url_for('auth.login_register'))
            else:
                flash(constant.UPDATE_FAIL)
        else:
            flash(constant.WRONG_PWD)

    return render_template("password_settings.html", user=current_user, form=form, base64=base64)


@auth.route('/admin', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_index():
    """管理员界面"""
    return render_template('auth/admin_index.html')


@auth.route('/add/category', methods=['GET', 'POST'])
@login_required
@admin_required
def add_category():
    """添加话题类别"""
    form = InsertCategory()
    if form.validate_on_submit():
        if not TopicCategory.query.filter_by(category_name=form.category_name.data).first():
            is_success = TopicCategory.insert_category(form.category_name.data, form.category_desc.data)
            if not is_success:
                flash(constant.FAIL)
        else:
            flash(constant.ALREADY_EXIST)
        return redirect(url_for('auth.manage_category'))

    return render_template('auth/add_category.html', form=form)


@auth.route('/manage/category', methods=['GET'])
@login_required
@admin_required
def manage_category():
    page = request.args.get('page', 1, type=int)
    pagination = base_pagination(TopicCategory.query, page, 'ADMIN_MANAGE')

    return render_template("auth/manage_category.html", endpoint='auth.manage_category',
                           pagination=pagination, items=pagination.items)


@auth.route('/delete/category', methods=['GET'])
@login_required
@admin_required
def delete_category():
    cate_id = request.args.get("cate_id", None)
    if not cate_id:
        return redirect(url_for('auth.manage_category'))
    is_success = TopicCategory.delete_category(cate_id)
    if not is_success:
        flash(constant.FAIL)
    else:
        flash(constant.UPDATE_SUCC)
    return redirect(url_for('auth.manage_category'))


@auth.route('/add/topic', methods=['GET', 'POST'])
@login_required
@admin_required
def add_topic():
    form = InsertTopic()
    if request.method == 'POST':
        if not Topic.query.filter_by(topic_name=form.topic_name.data).first():
            is_success = Topic.insert_topic(form.topic_name.data, form.topic_desc.data,
                                            request.files['file'].read(), form.topic_cate.data)
            if not is_success:
                flash(constant.FAIL)
        else:
            flash(constant.ALREADY_EXIST)
        return redirect(url_for('auth.manage_topic'))

    return render_template('auth/add_topic.html', form=form)


@auth.route('/manage/topic', methods=['GET'])
@login_required
@admin_required
def manage_topic():
    page = request.args.get('page', 1, type=int)
    pagination = base_pagination(Topic.query, page, 'ADMIN_MANAGE')

    return render_template("auth/manage_topic.html", endpoint='auth.manage_topic',
                           pagination=pagination, items=pagination.items)


@auth.route('/delete/topic', methods=['GET'])
@login_required
@admin_required
def delete_topic():
    topic_id = request.args.get("topic_id", None)
    if not topic_id:
        return redirect(url_for('auth.manage_topic'))
    is_success = Topic.delete_topic(topic_id)
    if not is_success:
        flash(constant.FAIL)
    else:
        flash(constant.UPDATE_SUCC)
    return redirect(url_for('auth.manage_topic'))


@auth.route('/manage/users', methods=['GET'])
@login_required
@admin_required
def manage_users():
    users = User.query.filter(User.username != current_user.username).all()
    return render_template("auth/manage_users.html", users=users)


@auth.route('/setting_users/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def setting_users(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        db.session.add(user)
        db.session.commit()
        flash(constant.PROFILE_UPDATE)
        return redirect(url_for('auth.setting_users', id=id))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    return render_template('auth/admin_edit_profile.html', form=form)

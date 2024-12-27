import request from '../utils/request';

export const login = (data) => {
  const params = new URLSearchParams();
  params.append('username', data.username);
  params.append('password', data.password);
  
  return request({
    url: '/token',
    method: 'post',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    data: params
  });
};

export const register = (data) => {
  return request({
    url: '/users/register',
    method: 'post',
    data,
  });
};

export const getUserList = (params) => {
  return request({
    url: '/users',
    method: 'get',
    params,
  });
};


export const updateUser = (id, role) => {
  return request({
    url: `/users/${id}`,
    method: 'put',
    params: {
      user_role: role
    }
  });
};

export const deleteUser = (id) => {
  return request({
    url: `/users/${id}`,
    method: 'delete',
  });
};
